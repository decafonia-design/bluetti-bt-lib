import asyncio
import logging
from decimal import Decimal

import async_timeout
from typing import Any, Callable, List, cast
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .encryption import BluettiEncryption, Message, MessageType, AES_BLOCK_SIZE
from ..base_devices import BluettiDevice
from ..const import NOTIFY_UUID, WRITE_UUID
from ..fields import FieldName
from ..registers import ReadableRegisters, DeviceRegister
from ..utils.privacy import mac_loggable

# A station needs a moment after the pack selector is written before its pack
# registers hold the data of the newly selected pack.
PACK_SELECTOR_SETTLE_SECONDS = 3


class DeviceReaderConfig:
    def __init__(self, timeout: int = 60, use_encryption: bool = False):
        self.timeout = timeout
        self.use_encryption = use_encryption


class DeviceReader:
    def __init__(
        self,
        mac: str,
        bluetti_device: BluettiDevice,
        future_builder_method: Callable[[], asyncio.Future[Any]],
        config: DeviceReaderConfig = DeviceReaderConfig(),
        lock: asyncio.Lock | None = None,
        ble_client: BleakClient | None = None,
    ):
        self.mac = mac
        self.bluetti_device = bluetti_device
        self.create_future = future_builder_method
        self.config = config
        self.polling_lock = lock or asyncio.Lock()

        self.ble_client = ble_client
        """Used for unittests"""

        self.logger = logging.getLogger(
            f"{__name__}.{mac_loggable(mac).replace(':', '_')}"
        )

        self.device = None
        self.client = None

        self.has_notifier = False
        self._notified_client = None
        """Client whose notify subscription is confirmed live. Only set
        after start_notify() succeeds, so a failed setup is retried."""
        self.current_registers = None
        self.notify_response = bytearray()
        self.notify_future: asyncio.Future[Any] | None = None
        self.encryption = BluettiEncryption()
        self.encrypted_buffer = bytearray()
        self._connected = False

    async def connect(self) -> bool:
        """Establish a persistent connection to the device.
        
        Note: This method should be called while holding the polling_lock
        to avoid race conditions. The read() method handles this automatically.
        """
        if self._connected and self.client and self.client.is_connected:
            return True

        try:
            if self.ble_client:
                self.device = None
            else:
                self.device = await BleakScanner.find_device_by_address(
                    self.mac, timeout=5
                )

                if self.device is None:
                    self.logger.error("Device not found")
                    return False

            self.logger.debug("Connecting to device")

            if self.ble_client:
                self.client = self.ble_client
            else:
                self.client = await establish_connection(
                    BleakClientWithServiceCache,
                    self.device,
                    self.device.name or "Unknown Device",
                    max_attempts=10,
                )

            # _notified_client tracks the client whose subscription is
            # confirmed live. has_notifier records that a subscription
            # exists (or may exist) on the current client so disconnect()
            # can stop it even when start_notify() raised after already
            # registering the callback. Because _notified_client is only
            # set on success, a failed setup is retried by the next
            # connect() instead of being skipped as already subscribed.
            if self.client is not self._notified_client:
                self.has_notifier = True
                await self.client.start_notify(
                    NOTIFY_UUID, self._notification_handler
                )
                self._notified_client = self.client

            self.logger.debug("Connected to device")

            if self.config.use_encryption:
                while not self.encryption.is_ready_for_commands:
                    await asyncio.sleep(1)
                    self.logger.debug("Waiting for encryption handshake...")

            self._connected = True
            return True

        except BleakError as err:
            self.logger.warning("Bleak error during connect: %s", err)
            await self._cleanup_failed_connect()
            return False
        except asyncio.CancelledError:
            # Home Assistant cancels tasks on reload/unload. Tear down
            # whatever we started, then let the cancellation propagate
            # instead of reporting it as an ordinary connection failure.
            await self._cleanup_failed_connect()
            raise
        except BaseException as err:
            self.logger.warning("Unknown error during connect: %s", err)
            await self._cleanup_failed_connect()
            return False

    async def _mark_disconnected(self) -> None:
        """Forget a connection that the device or the stack dropped.

        The notify subscription and the encryption session are only valid
        for the lifetime of a single connection, so they are cleared here
        as well. Without this, the next connect() would see the stale
        has_notifier flag, skip start_notify() on the replacement client
        and then never receive a response again. The stale client is
        disconnected too (when we own it) so a fresh connect cannot
        stack a second connection on top of a half-dead one.
        """
        self._connected = False
        self.has_notifier = False
        self._notified_client = None
        self.encryption.reset()
        self.encrypted_buffer.clear()

        if self.ble_client is None and self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
            except Exception:
                pass

    async def _cleanup_failed_connect(self) -> None:
        """Tear down a half-established connection.

        If connect() fails after the client was created (for example the
        encryption handshake never completed), leaving that client
        connected would leak it: the next connect() would open a second
        connection to the device instead of starting from a clean state.

        A caller-supplied ble_client is not ours to tear down; the
        caller cleans it up through disconnect().
        """
        if self.ble_client is not None:
            return

        self._connected = False

        if self.has_notifier and self.client:
            try:
                await self.client.stop_notify(NOTIFY_UUID)
            except Exception:
                pass
            self.has_notifier = False
            self._notified_client = None

        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
            except Exception:
                pass

        self.encryption.reset()
        self.encrypted_buffer.clear()

    async def disconnect(self):
        """Clean up the reader's notification and connection state."""
        async with self.polling_lock:
            if self.has_notifier and self.client:
                try:
                    await self.client.stop_notify(NOTIFY_UUID)
                    self.logger.debug("Stopped notifier")
                except Exception:
                    pass
                self.has_notifier = False
                self._notified_client = None

            # Only disconnect clients created and managed by this reader.
            # A supplied ble_client belongs to the caller.
            if (
                self.ble_client is None
                and self.client
                and self.client.is_connected
            ):
                await self.client.disconnect()
                self.logger.debug("Disconnected from device")

            self.encryption.reset()
            self.encrypted_buffer.clear()
            self._connected = False

    @staticmethod
    def _pack_has_data(pack_data: dict) -> bool:
        """Whether a pack slot is actually occupied.

        An empty slot answers every pack register with zero. A real pack
        always reports a voltage, even when it is fully drained, so an
        all-zero answer means nothing is sitting in that slot.
        """
        for value in pack_data.values():
            if isinstance(value, bytes):
                if value.strip(b"\x00"):
                    return True
            elif isinstance(value, (int, Decimal)):
                if value:
                    return True
            elif value:
                return True

        return False

    async def read(
        self, only_registers: List[ReadableRegisters] | None = None, raw: bool = False
    ) -> dict | None:

        registers = self.bluetti_device.get_polling_registers()
        pack_registers = self.bluetti_device.get_pack_polling_registers()

        if only_registers is not None:
            registers = only_registers
            pack_registers = []

        parsed_data: dict = {}

        self.logger.debug("Reading device registers")

        async with self.polling_lock:
            try:
                async with async_timeout.timeout(self.config.timeout):
                    if not self._connected:
                        if not await self.connect():
                            return None

                    self.logger.debug("Connected to device")

                    if self.config.use_encryption:
                        while not self.encryption.is_ready_for_commands:
                            await asyncio.sleep(1)
                            self.logger.debug("Waiting for encryption handshake...")

                    for register in registers:
                        body = register.parse_response(
                            await self._async_send_command(register)
                        )

                        self.logger.debug("Raw data: %s", body)

                        if raw:
                            d = {}
                            d[register.starting_address] = body
                            parsed_data.update(d)
                            continue

                        parsed = self.bluetti_device.parse(
                            register.starting_address, body
                        )

                        self.logger.debug("Parsed data: %s", parsed)

                        parsed_data.update(parsed)

                    # Register 96 counts the packs that are installed, but it
                    # does not say which slots they occupy: an AC300 holding
                    # packs in slots 2, 3 and 4 still reports 3. So the walk
                    # covers every slot the station can hold, and stops early
                    # once the reported number of packs have answered.
                    installed = parsed_data.get(FieldName.PACK_NUM.value)
                    if not isinstance(installed, int) or installed < 0:
                        # Profile without a pack_num field, or a bad reading.
                        installed = None
                    if raw:
                        # Raw scans report every slot, empty ones included.
                        installed = None

                    slot_limit = self.bluetti_device.max_packs if pack_registers else 0
                    slots: list[int] = []

                    for pack in range(1, slot_limit + 1):
                        if installed is not None and len(slots) >= installed:
                            break

                        body = register.parse_response(
                            await self._async_send_command(
                                self.bluetti_device.get_pack_selector(pack),
                            )
                        )

                        # We need to wait for the powerstation to populate all registers
                        await asyncio.sleep(PACK_SELECTOR_SETTLE_SECONDS)

                        pack_data: dict = {}

                        for register in pack_registers:
                            body = register.parse_response(
                                await self._async_send_command(register)
                            )

                            self.logger.debug("Raw data: %s", body)

                            if raw:
                                pack_data[register.starting_address] = body
                                continue

                            parsed = self.bluetti_device.parse(
                                register.starting_address,
                                body,
                                pack_num=pack,
                            )

                            self.logger.debug("Parsed data: %s", parsed)

                            pack_data.update(parsed)

                        if raw or self._pack_has_data(pack_data):
                            parsed_data.update(pack_data)
                            slots.append(pack)
                        else:
                            self.logger.debug(
                                "Pack slot %s answered with nothing, treating it as empty",
                                pack,
                            )

                    # Tell the consumer which slots hold a pack. Key presence on
                    # its own cannot say whether a slot is empty or a pack that
                    # just failed to answer, and a consumer that hides entities
                    # needs that difference to stay stable.
                    if pack_registers and not raw:
                        parsed_data[FieldName.PACK_SLOTS.value] = slots

                    if installed is not None and len(slots) != installed:
                        self.logger.debug(
                            "Station reported %s packs, %s answered in slots 1-%s",
                            installed,
                            len(slots),
                            slot_limit,
                        )

            except TimeoutError:
                self.logger.warning("Timeout")
                return None
            except BleakError as err:
                self.logger.warning("Bleak error: %s", err)
                # Connection may be lost: drop all per-connection state so
                # the next read() reconnects with a fresh client, notifier
                # and encryption handshake.
                await self._mark_disconnected()
                return None
            except asyncio.CancelledError:
                # External cancellation (e.g. HA reload/unload); the
                # connection state is now uncertain, so drop it and let
                # the cancellation propagate. The timeout above is
                # converted to TimeoutError by async_timeout before it
                # can reach this handler.
                await self._mark_disconnected()
                raise
            except BaseException as err:
                self.logger.warning("Unknown error %s", err)
                return None

            # Check if dict is empty
            if not parsed_data:
                return None

            return parsed_data

    async def read_locked(
        self, only_registers: List[ReadableRegisters], raw: bool = False
    ) -> dict | None:
        """Read selected registers while the caller holds polling_lock."""
        parsed_data: dict = {}

        try:
            async with async_timeout.timeout(self.config.timeout):
                if not self._connected:
                    if not await self.connect():
                        return None

                if self.config.use_encryption:
                    while not self.encryption.is_ready_for_commands:
                        await asyncio.sleep(1)

                for register in only_registers:
                    body = register.parse_response(
                        await self._async_send_command(register)
                    )

                    if raw:
                        parsed_data[register.starting_address] = body
                    else:
                        parsed_data.update(
                            self.bluetti_device.parse(
                                register.starting_address, body
                            )
                        )

        except TimeoutError:
            self.logger.warning("Timeout reading selected registers")
            return None
        except BleakError as err:
            self.logger.warning("Bleak error reading selected registers: %s", err)
            # Same recovery path as read(): the next read/read_locked()
            # reconnects from scratch.
            await self._mark_disconnected()
            return None
        except asyncio.CancelledError:
            await self._mark_disconnected()
            raise
        except BaseException as err:
            self.logger.warning("Error reading selected registers: %s", err)
            return None

        return parsed_data or None

    async def _async_send_command(self, registers: DeviceRegister) -> bytes:
        """Send command and return response"""
        self.current_registers = registers
        self.notify_response = bytearray()
        self.notify_future = self.create_future()
        self.encrypted_buffer.clear()

        command_bytes = bytes(registers)

        # Encrypt command
        if self.config.use_encryption is True:
            if not self.encryption.is_ready_for_commands:
                return bytes()
            command_bytes = self.encryption.aes_encrypt(
                command_bytes, self.encryption.secure_aes_key, None
            )

        try:
            # Make request
            await self.client.write_gatt_char(WRITE_UUID, command_bytes)

            self.logger.debug("Request sent (%s)", registers)

            # Wait for response
            res = await asyncio.wait_for(self.notify_future, timeout=5)

            self.logger.debug("Got response (%d bytes)", len(res))

            return cast(bytes, res)
        except BleakError:
            # A failed GATT write/notify almost always means the
            # connection is gone. Propagate it so the caller's
            # BleakError handler can drop the dead connection and
            # reconnect on the next poll; swallowing it here would
            # leave _connected stuck at True forever.
            raise
        except asyncio.TimeoutError:
            # The GATT link can still look healthy when the device skips
            # a response: log enough context to tell a dead connection
            # from a single missed notification. Recovery policy (e.g. a
            # consecutive-timeout threshold) is deliberately not applied
            # here yet.
            self.logger.debug(
                "No notification for %s within 5s (client connected: %s)",
                registers,
                self.client.is_connected if self.client else False,
            )
        except Exception:
            self.logger.warning("Error while reading data", exc_info=True)

        return bytes()

    def _calculate_expected_encrypted_length(self, buffer: bytearray) -> int | None:
        """Calculate expected total length of an encrypted message."""
        if len(buffer) < 2:
            return None

        data_len = (buffer[0] << 8) + buffer[1]

        key, iv = self.encryption.getKeyIv()
        if iv is None:
            header_size = 6
        else:
            header_size = 2

        padded_len = (
            (data_len + AES_BLOCK_SIZE - 1) // AES_BLOCK_SIZE
        ) * AES_BLOCK_SIZE

        return header_size + padded_len

    async def _notification_handler(self, _: int, data: bytearray):
        """Handle bt data."""
        self.logger.debug("Got new data (%d bytes)", len(data))

        if self.config.use_encryption is True:
            message = Message(data)

            if message.is_pre_key_exchange:
                message.verify_checksum()

                if message.type == MessageType.CHALLENGE:
                    challenge_response = self.encryption.msg_challenge(message)
                    await self.client.write_gatt_char(WRITE_UUID, challenge_response)
                    return

                if message.type == MessageType.CHALLENGE_ACCEPTED:
                    self.logger.debug("Challenge accepted")
                    return

                return

            if self.encryption.unsecure_aes_key is None:
                self.logger.error(
                    "Received encrypted message before key initialization"
                )
                return

            self.encrypted_buffer.extend(data)

            expected_len = self._calculate_expected_encrypted_length(
                self.encrypted_buffer
            )

            if expected_len is None:
                return

            if len(self.encrypted_buffer) < expected_len:
                self.logger.debug(
                    "Buffering fragment: %d/%d bytes",
                    len(self.encrypted_buffer),
                    expected_len,
                )
                return

            complete_message = bytes(self.encrypted_buffer[:expected_len])

            if len(self.encrypted_buffer) > expected_len:
                self.encrypted_buffer = self.encrypted_buffer[expected_len:]
            else:
                self.encrypted_buffer.clear()

            key, iv = self.encryption.getKeyIv()

            try:
                decrypted = Message(
                    self.encryption.aes_decrypt(complete_message, key, iv)
                )
            except ValueError as e:
                self.logger.error("Decryption failed: %s", e)
                self.encrypted_buffer.clear()
                return

            if decrypted.is_pre_key_exchange:
                decrypted.verify_checksum()

                if decrypted.type == MessageType.PEER_PUBKEY:
                    peer_pubkey_response = self.encryption.msg_peer_pubkey(decrypted)
                    await self.client.write_gatt_char(WRITE_UUID, peer_pubkey_response)
                    return

                if decrypted.type == MessageType.PUBKEY_ACCEPTED:
                    self.encryption.msg_key_accepted(decrypted)
                    return

            # Handle as message
            data = decrypted.buffer

        # Save data
        self.notify_response.extend(data)

        # The connection is persistent, so notifications can arrive outside of
        # a pending command (leftovers, write acknowledgements, ...). Only the
        # future of the running command may be resolved here.
        if self.notify_future is None or self.notify_future.done():
            self.logger.debug(
                "Notification (%d bytes) arrived with no pending command",
                len(data),
            )
            return

        self.notify_future.set_result(self.notify_response)
