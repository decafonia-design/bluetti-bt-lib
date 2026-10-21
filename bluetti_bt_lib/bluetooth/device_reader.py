import asyncio
import logging
from decimal import Decimal

import async_timeout
from typing import Any, Callable, List, cast
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from cryptography.exceptions import InvalidSignature

from .encryption import BluettiEncryption, Message, MessageType, AES_BLOCK_SIZE
from ..base_devices import BluettiDevice
from ..const import NOTIFY_UUID, WRITE_UUID
from ..fields import FieldName
from ..registers import ReadableRegisters, DeviceRegister
from ..utils.privacy import mac_loggable

# A station needs a moment after the pack selector is written before its pack
# registers hold the data of the newly selected pack.
PACK_SELECTOR_SETTLE_SECONDS = 3

# A slot that holds a pack usually answers long before that wait is over, while
# an empty slot needs all of it. Take an early look and only wait out the
# remainder for a slot that came back empty, so a station with packs in most
# of its slots does not pay the full settle on every one.
PACK_SELECTOR_EARLY_LOOK_SECONDS = 1

# How long a single request waits for its answer.
RESPONSE_TIMEOUT_SECONDS = 5

# How long a fresh connection gets to finish its key exchange. The device
# starts the exchange on its own once notifications are on, so it normally
# takes a second or two.
HANDSHAKE_TIMEOUT_SECONDS = 20


class ResponseTimeout(Exception):
    """No valid answer to a request arrived in time.

    The link is left in an unknown state: an answer may still be on its way and
    would otherwise be taken for the next request, so the caller must stop using
    this connection instead of sending another command.
    """

    def __init__(self, registers: DeviceRegister):
        super().__init__(f"no valid response to {registers}")
        self.registers = registers


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
        self.last_notification: bytes | None = None
        """Raw bytes of the previous notification, used to drop repeats."""
        self.handshake_failed = False
        """Set when the key exchange cannot complete; only a reconnect fixes it."""
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
                self.handshake_failed = False
                if not await self._await_handshake():
                    await self._abandon_handshake()
                    return False

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
        self.last_notification = None

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
        self.last_notification = None

    async def _await_handshake(self) -> bool:
        """Wait for the key exchange of a fresh connection to finish.

        A failed exchange never recovers over a live link: the peer only sends
        a new challenge on a new connection. Waiting longer than the deadline
        would just burn the caller's timeout and leave a half-open connection
        behind, which the next connect() would stack a second link on top of.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + HANDSHAKE_TIMEOUT_SECONDS

        while not self.encryption.is_ready_for_commands:
            if self.handshake_failed:
                self.logger.warning(
                    "Key exchange failed, reconnecting on the next read"
                )
                return False

            if loop.time() >= deadline:
                self.logger.warning(
                    "Key exchange did not complete within %ss, reconnecting",
                    HANDSHAKE_TIMEOUT_SECONDS,
                )
                return False

            await asyncio.sleep(1)
            self.logger.debug("Waiting for encryption handshake...")

        return True

    async def _abandon_handshake(self) -> None:
        """Tear down a link whose key exchange cannot complete.

        Unlike _mark_disconnected() this also closes a caller-supplied client:
        a live link without a session can never carry a command, and dropping
        it is the only way to get the peer to restart the exchange. The owner
        of a supplied client rebuilds the connection from its disconnect
        callback.
        """
        self.handshake_failed = False
        self._connected = False
        self.current_registers = None
        self.notify_response = bytearray()
        self.notify_future = None

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
        self.last_notification = None

    async def _resync_link(self) -> None:
        """Reset the notification pipeline without dropping the connection.

        A request that got no valid answer leaves the link desynced: an answer
        may still be on its way and would otherwise be handed to the next
        request. Unsubscribing discards whatever is in flight, and clearing the
        subscription flags makes the next connect() subscribe again.

        Unlike _mark_disconnected() this keeps the encryption session: the
        device only restarts a handshake when the connection itself drops, so
        resetting the session over a live link would wedge the device. The
        connection is not ours to drop either when a client was supplied.
        """
        self.logger.debug("Resyncing the notification pipeline")

        self.current_registers = None
        self.notify_response = bytearray()
        self.notify_future = None
        self.encrypted_buffer.clear()
        self.last_notification = None

        if self.has_notifier and self.client:
            try:
                await self.client.stop_notify(NOTIFY_UUID)
            except Exception:
                pass
            self.has_notifier = False
            self._notified_client = None

        self._connected = False

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
            self.last_notification = None
            self._connected = False

    async def _read_pack(
        self, pack: int, pack_registers: List[ReadableRegisters], raw: bool
    ) -> dict:
        """Read the pack registers of the slot the selector points at."""
        pack_data: dict = {}

        for register in pack_registers:
            body = register.parse_response(await self._async_send_command(register))

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

        return pack_data

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

                    if self.config.use_encryption and not (
                        self.encryption.is_ready_for_commands
                    ):
                        # connect() only reports success with a finished
                        # exchange, so the session broke since the link came
                        # up. Only a new connection makes the peer issue a
                        # fresh challenge.
                        self.logger.warning(
                            "Encryption session is not ready, reconnecting"
                        )
                        await self._abandon_handshake()
                        return None

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

                        # We need to wait for the powerstation to populate all
                        # registers, but a loaded slot is usually ready before
                        # that wait is over: look early, and only wait out the
                        # remainder for a slot that came back empty.
                        early_look = min(
                            PACK_SELECTOR_EARLY_LOOK_SECONDS,
                            PACK_SELECTOR_SETTLE_SECONDS,
                        )
                        await asyncio.sleep(early_look)

                        pack_data = await self._read_pack(pack, pack_registers, raw)

                        if not raw and not self._pack_has_data(pack_data):
                            await asyncio.sleep(
                                PACK_SELECTOR_SETTLE_SECONDS - early_look
                            )
                            pack_data = await self._read_pack(pack, pack_registers, raw)

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

            except ResponseTimeout as err:
                # Stop here rather than sending more commands: the answer to
                # this request may still arrive and would be read as the answer
                # to the next one, which is how a register ends up holding the
                # value of a different register.
                self.logger.warning("Read aborted: %s", err)
                await self._resync_link()
                return None
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

                if self.config.use_encryption and not (
                    self.encryption.is_ready_for_commands
                ):
                    # Same recovery as read(): the next call reconnects.
                    self.logger.warning(
                        "Encryption session is not ready, reconnecting"
                    )
                    await self._abandon_handshake()
                    return None

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

        except ResponseTimeout as err:
            # Same reasoning as read(): a write verification read-back that
            # gets no valid answer must not be followed by another command on
            # a link that may still be carrying a late answer.
            self.logger.warning("Read aborted: %s", err)
            await self._resync_link()
            return None
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
        """Send a command and return its validated response.

        Raises ResponseTimeout when no valid answer arrives in time; the caller
        must then stop using this connection. A MODBUS exception answer (for
        example a register range the device does not support) returns an empty
        response.
        """
        self.current_registers = registers
        self.notify_response = bytearray()
        self.notify_future = self.create_future()
        self.encrypted_buffer.clear()
        # Two identical answers to two different requests are legitimate.
        self.last_notification = None

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
            res = await asyncio.wait_for(
                self.notify_future, timeout=RESPONSE_TIMEOUT_SECONDS
            )

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
            # No valid answer to this request. The GATT link can still look
            # healthy while the device skipped a response, but the answer may
            # also still be on its way: keep going would hand that answer to
            # the next request, which is how a register ends up holding the
            # value of a different one. Abort the read instead.
            self.logger.warning(
                "No valid response to %s within %ss (client connected: %s)",
                registers,
                RESPONSE_TIMEOUT_SECONDS,
                self.client.is_connected if self.client else False,
            )
            raise ResponseTimeout(registers) from None
        finally:
            # Answers that arrive from now on are not for a pending request.
            self.notify_future = None

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

    async def _write_handshake(self, payload: bytes, what: str) -> bool:
        """Send a key exchange reply.

        A BleakError raised inside a notification callback is swallowed by
        bleak's dispatch, which leaves the read waiting its full timeout with
        nothing in the log naming the cause. Catching it here and flagging the
        handshake lets the read give the connection up instead.
        """
        try:
            await self.client.write_gatt_char(WRITE_UUID, payload)
            return True
        except BleakError as err:
            self.logger.warning("Failed to send the %s: %s", what, err)
            self.handshake_failed = True
            return False

    async def _notification_handler(self, _: int, data: bytearray):
        """Handle bt data."""
        self.logger.debug("Got new data (%d bytes)", len(data))

        # Some stations (the Apex 300 among them) deliver every frame two or
        # three times, and retry the key exchange until they see our answer.
        # Replying to a repeat makes a second local keypair, so the peer ends
        # up sharing a secret with a key we threw away: the handshake is
        # confirmed on both sides and the device then ignores every command.
        # A half-assembled answer is exempt, because its next chunk has to be
        # kept even when it looks exactly like the chunk before it.
        notification = bytes(data)
        if notification == self.last_notification and not self.notify_response:
            self.logger.debug("Duplicate notification ignored")
            return
        self.last_notification = notification

        if self.config.use_encryption is True:
            message = Message(data)

            if message.is_pre_key_exchange:
                message.verify_checksum()

                try:
                    message_type = message.type
                except ValueError:
                    # Unknown frame. bleak runs this callback as a detached
                    # task, so raising here is silent and the read hangs.
                    self.logger.warning("Unknown key exchange message type")
                    return

                if message_type == MessageType.CHALLENGE:
                    challenge_response = self.encryption.msg_challenge(message)
                    if challenge_response is not None:
                        await self._write_handshake(
                            challenge_response, "challenge response"
                        )
                    return

                if message_type == MessageType.CHALLENGE_ACCEPTED:
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

                try:
                    decrypted_type = decrypted.type
                except ValueError:
                    self.logger.warning("Unknown key exchange message type")
                    return

                if decrypted_type == MessageType.CHALLENGE:
                    # A device can restart the exchange inside the encrypted
                    # channel. This is what refreshes the IV that the peer
                    # pubkey is later verified against, so skipping it makes
                    # every following pubkey signature look invalid.
                    challenge_response = self.encryption.msg_challenge(decrypted)
                    if challenge_response is not None:
                        await self._write_handshake(
                            self.encryption.aes_encrypt(challenge_response, key, None),
                            "challenge response",
                        )
                    return

                if decrypted_type == MessageType.CHALLENGE_ACCEPTED:
                    self.logger.debug("Challenge accepted (encrypted)")
                    return

                if decrypted_type == MessageType.PEER_PUBKEY:
                    try:
                        peer_pubkey_response = self.encryption.msg_peer_pubkey(
                            decrypted
                        )
                    except InvalidSignature:
                        # Almost always a stale IV: drop the session and let
                        # the next connection restart the exchange rather than
                        # leaving the link wedged.
                        self.logger.warning(
                            "Peer pubkey signature rejected, reconnecting"
                        )
                        self.encryption.reset()
                        self.encrypted_buffer.clear()
                        self.handshake_failed = True
                        return
                    await self._write_handshake(
                        peer_pubkey_response, "peer pubkey reply"
                    )
                    return

                if decrypted_type == MessageType.PUBKEY_ACCEPTED:
                    try:
                        self.encryption.msg_key_accepted(decrypted)
                    except (ValueError, AttributeError) as err:
                        self.logger.warning("Key exchange rejected: %s", err)
                        self.handshake_failed = True
                    return

                # A key exchange frame is never MODBUS data.
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

        registers = self.current_registers
        if registers is None:
            return

        response = bytes(self.notify_response)

        if registers.is_valid_exception(response):
            # A register range this device does not answer. Replying with
            # nothing keeps those fields out of the result instead of failing
            # the whole poll.
            self.logger.debug(
                "Exception response to %s: %s", registers, response.hex()
            )
            self.notify_future.set_result(bytes())
            return

        size = registers.response_size()
        if len(response) < size:
            self.logger.debug(
                "Partial answer (%d/%d bytes), waiting for the rest",
                len(response),
                size,
            )
            return

        if len(response) == size and registers.is_valid_response(response):
            self.notify_future.set_result(response)
            return

        # Not the answer to this request: a late answer to an earlier one, a
        # write acknowledgement, or a corrupted frame. A function 03 answer
        # carries no register address, so length plus byte count is the only
        # thing to go on. Discard it and keep waiting; if no valid answer
        # follows, the request times out and the read is aborted.
        self.logger.debug(
            "Discarding response that does not match %s: %s",
            registers,
            response.hex(),
        )
        self.notify_response = bytearray()
