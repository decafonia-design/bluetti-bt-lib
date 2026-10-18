import asyncio
import logging
import struct
from typing import Any
from dataclasses import dataclass

import async_timeout
from bleak import BleakClient
from bleak.exc import BleakError

from .encryption import AES_BLOCK_SIZE, BluettiEncryption, Message, MessageType
from ..const import NOTIFY_UUID, WRITE_UUID
from ..base_devices import BluettiDevice
from ..utils.privacy import mac_loggable
from .device_reader import DeviceReader
from ..registers import ReadableRegisters, WriteableRegister
from ..devices.charger2 import CHARGER2, CHARGER2_CONTROL_STATES

@dataclass
class WriteVerificationResult:
    """Result of writing a field and reading its state back from the device."""

    write_succeeded: bool
    readback_succeeded: bool
    values: dict[str, Any] | None = None
    verified: bool = False

class DeviceWriterConfig:
    def __init__(self, timeout: int = 15, use_encryption: bool = False):
        self.timeout = timeout
        self.use_encryption = use_encryption


def _select_verification_delay(field_obj, is_shared_control: bool) -> float:
    """Pick how long to wait after a write before reading it back.

    A field can declare its own delay in the device config (slow-to-apply
    settings such as the AC300 SOC range thresholds); otherwise Charger 2
    shared controls use the extended delay and everything else the short
    default.
    """
    if field_obj is not None and field_obj.verification_delay is not None:
        return field_obj.verification_delay
    return 2.0 if is_shared_control else 0.5


class DeviceWriter:
    def __init__(
        self,
        bleak_client: BleakClient,
        bluetti_device: BluettiDevice,
        config: DeviceWriterConfig = DeviceWriterConfig(),
        lock: asyncio.Lock | None = None,
        reader: DeviceReader | None = None,
    ):
        self.client = bleak_client
        self.reader = reader
        self.bluetti_device = bluetti_device
        self.config = config
        self.polling_lock = lock or asyncio.Lock()
        self.encryption = BluettiEncryption()
        self.encrypted_buffer = bytearray()
        self.encryption_ready = asyncio.Event()
        self.has_notifier = False
        self._connected = False
        self._owns_notifier = False
        self._borrowed_encryption = False
        self._attached = False
        """True when the client belongs to a DeviceReader's shared connection."""
        self._write_future: asyncio.Future[bytes] | None = None

        self.logger = logging.getLogger(
            f"{__name__}.{mac_loggable(bleak_client.address).replace(':', '_')}"
        )

    def attach(self, encryption: BluettiEncryption | None = None) -> None:
        """Attach to a client that is already connected and notifying.

        Use this when a DeviceReader and a DeviceWriter share a single
        persistent connection. The notifier (and with it the encryption
        handshake) belongs to the reader, so the writer must not start a
        second one on the same characteristic and cannot wait for write
        acknowledgements it never receives.

        The client itself belongs to the reader as well: disconnect() on
        an attached writer leaves the shared connection alone for the
        reader to tear down.
        """
        self._connected = True
        self._attached = True
        if encryption is not None:
            # Share the session instead of copying keys, so both sides stay
            # in sync for the lifetime of the connection. It is not ours to
            # reset on disconnect.
            self.encryption = encryption
            self._borrowed_encryption = True
        self.encryption_ready.set()

    async def connect(self) -> bool:
        """Establish a persistent connection to the device.
        
        Note: This method should be called while holding the polling_lock
        to avoid race conditions. The write() method handles this automatically.
        """
        if self._connected and self.client.is_connected:
            return True

        try:
            if not self.client.is_connected:
                self.logger.debug("Connecting to device")
                await self.client.connect()

            if (
                self.config.use_encryption
                and not self._attached
                and not self._owns_notifier
            ):
                # An attached writer never owns a notifier: the reader
                # owns the subscription and the handshake on the shared
                # connection. A standalone writer must (re-)subscribe on
                # every new connection: reconnecting reopens the GATT
                # connection on the same client object, so the previous
                # subscription and handshake are gone even though the
                # Python object identity has not changed.
                self.encryption_ready.clear()
                await self.client.start_notify(
                    NOTIFY_UUID, self._notification_handler
                )
                self.has_notifier = True
                self._owns_notifier = True
                await asyncio.wait_for(
                    self.encryption_ready.wait(),
                    timeout=self.config.timeout,
                )

            self.logger.debug("Connected to device")
            self._connected = True
            return True

        except BleakError as err:
            self.logger.warning("Bleak error during connect: %s", err)
            await self._mark_disconnected()
            return False
        except asyncio.CancelledError:
            # Propagate cancellation (HA reload/unload) after tearing
            # down whatever this connect attempt started.
            await self._mark_disconnected()
            raise
        except BaseException as err:
            self.logger.warning("Unknown error during connect: %s", err)
            await self._mark_disconnected()
            return False

    async def _mark_disconnected(self) -> None:
        """Forget a dropped or half-established connection.

        Reconnecting reopens the GATT connection on the same client
        object, so the notify subscription and the encryption handshake
        are gone with it even though the Python object identity has not
        changed. A standalone writer must therefore re-subscribe and
        re-run the handshake on the next connect(), so its notifier
        ownership state and session are cleared here. An attached
        writer leaves the reader's notifier, session and client alone.
        """
        self._connected = False

        if self._attached:
            return

        self.has_notifier = False
        self._owns_notifier = False
        if not self._borrowed_encryption:
            self.encryption.reset()
        self.encrypted_buffer.clear()
        self.encryption_ready.clear()

        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
            except Exception:
                pass

    async def disconnect(self):
        """Disconnect from the device."""
        if not self._connected:
            return

        async with self.polling_lock:
            if self.has_notifier:
                try:
                    await self.client.stop_notify(NOTIFY_UUID)
                except BleakError:
                    pass
                self.has_notifier = False

            # Only disconnect clients that this writer established.
            # When attached, the client belongs to the reader: pulling
            # it down here would kill the reader's connection while the
            # reader still believes it is connected.
            if (
                not self._attached
                and self.client
                and self.client.is_connected
            ):
                await self.client.disconnect()
                self.logger.debug("Disconnected from device")

            if not self._borrowed_encryption:
                self.encryption.reset()
            self.encrypted_buffer.clear()
            self.encryption_ready.clear()
            self._connected = False
            self._attached = False


    async def write(self, field: str, value: Any) -> bool:
        """Write a field, retaining the existing boolean API."""
        return await self._write(field, value, verify=False)

    async def write_verified(
        self, field: str, value: Any
    ) -> WriteVerificationResult:
        """Write a field and read back its actual device state."""
        result = await self._write(field, value, verify=True)
        assert isinstance(result, WriteVerificationResult)
        return result

    async def _write(
        self, field: str, value: Any, verify: bool
    ) -> bool | WriteVerificationResult:
        available_fields = {f.name: f for f in self.bluetti_device.fields}
        field_obj = available_fields.get(field)

        if field_obj is None:
            self.logger.error("Field not supported: %s", field)
            return (
                WriteVerificationResult(False, False)
                if verify
                else False
            )

        if verify and self.reader is None:
            self.logger.error("Verified writes require a DeviceReader")
            return WriteVerificationResult(False, False)

        control_fields = {
            "ctrl_system_on_off": 0,
            "ctrl_silent_charging": 1,
        }
        is_shared_control = (
            isinstance(self.bluetti_device, CHARGER2)
            and field in control_fields
        )

        if is_shared_control:
            if not isinstance(value, bool):
                self.logger.error("Charger 2 control value must be bool")
                return (
                    WriteVerificationResult(False, False)
                    if verify
                    else False
                )
            if self.reader is None:
                self.logger.error(
                    "Charger 2 control requires a reader for register 15600"
                )
                return (
                    WriteVerificationResult(False, False)
                    if verify
                    else False
                )
            command = None
        else:
            command = self.bluetti_device.build_write_command(field, value)
            if command is None:
                self.logger.error("Field is not writeable: %s", field)
                return (
                    WriteVerificationResult(False, False)
                    if verify
                    else False
                )

        write_succeeded = False

        async with self.polling_lock:
            try:
                async with async_timeout.timeout(self.config.timeout):
                    if not self._connected:
                        if not await self.connect():
                            return (
                                WriteVerificationResult(False, False)
                                if verify
                                else False
                            )

                    if verify and self.config.use_encryption:
                        while not self.reader.encryption.is_ready_for_commands:
                            await asyncio.sleep(0.1)

                    if is_shared_control:
                        raw_data = await self.reader.read_locked(
                            [ReadableRegisters(15600, 1)],
                            raw=True,
                        )
                        raw_word = raw_data.get(15600) if raw_data else None

                        if raw_word is None or len(raw_word) != 2:
                            self.logger.warning(
                                "Unable to read valid Charger 2 register 15600"
                            )
                            return (
                                WriteVerificationResult(False, False)
                                if verify
                                else False
                            )

                        current_word = struct.unpack("!H", raw_word)[0]
                        current_state = CHARGER2_CONTROL_STATES.get(current_word)

                        if current_state is None:
                            self.logger.warning(
                                "Unknown Charger 2 control value: 0x%04X",
                                current_word,
                            )
                            return (
                                WriteVerificationResult(False, False)
                                if verify
                                else False
                            )

                        state = list(current_state)
                        state[control_fields[field]] = value
                        new_state = tuple(state)

                        new_word = next(
                            (
                                word
                                for word, mapped_state
                                in CHARGER2_CONTROL_STATES.items()
                                if mapped_state == new_state
                            ),
                            None,
                        )
                        if new_word is None:
                            self.logger.error(
                                "No Charger 2 register value for state %s",
                                new_state,
                            )
                            return (
                                WriteVerificationResult(False, False)
                                if verify
                                else False
                            )

                        command = WriteableRegister(15600, new_word)

                    command_bytes = bytes(command)
                    if self.config.use_encryption:
                        command_bytes = self.encryption.aes_encrypt(
                            command_bytes,
                            self.encryption.secure_aes_key,
                            None,
                        )

                    self.logger.debug("Writing command: %s", command)

                    if self._owns_notifier:
                        self._write_future = (
                            asyncio.get_running_loop().create_future()
                        )

                    await self.client.write_gatt_char(WRITE_UUID, command_bytes)
                    write_succeeded = True

                    if self._write_future is not None:
                        try:
                            response = await asyncio.wait_for(
                                self._write_future, timeout=5
                            )
                            self.logger.debug(
                                "Write response received: %s", response.hex()
                            )
                        except asyncio.TimeoutError:
                            self.logger.warning("Write response timeout")
                            write_succeeded = False

                    if not verify:
                        return write_succeeded

                    if not write_succeeded:
                        return WriteVerificationResult(False, False)

                    # Allow the device time to apply the write before
                    # verification (see _select_verification_delay).
                    verification_delay = _select_verification_delay(
                        field_obj, is_shared_control
                    )
                    self.logger.debug(
                        "Write verification: device_class=%s field=%s "
                        "is_shared_control=%s delay=%.1fs",
                        type(self.bluetti_device).__name__,
                        field,
                        is_shared_control,
                        verification_delay,
                    )
                    await asyncio.sleep(verification_delay)
                    self.logger.debug(
                        "Write verification delay elapsed for %s; reading back",
                        field,
                    )

                    # Read back only the register(s) containing the requested field.
                    if is_shared_control:
                        raw_data = await self.reader.read_locked(
                            [ReadableRegisters(15600, 1)],
                            raw=True,
                        )
                        raw_word = raw_data.get(15600) if raw_data else None

                        if raw_word is None or len(raw_word) != 2:
                            self.logger.warning(
                                "Charger 2 write sent, but register 15600 "
                                "could not be read back"
                            )
                            return WriteVerificationResult(True, False)

                        actual_word = struct.unpack("!H", raw_word)[0]

                        self.logger.debug(
                            "Charger 2 register 15600 read-back: "
                            "raw=%s decoded=0x%04X expected_field=%s "
                            "requested=%r",
                            raw_word.hex(),
                            actual_word,
                            field,
                            value,
                        )

                        if actual_word not in CHARGER2_CONTROL_STATES:
                            self.logger.warning(
                                "Unknown Charger 2 read-back value: 0x%04X",
                                actual_word,
                            )
                            return WriteVerificationResult(True, False)

                        values = self.bluetti_device.parse(15600, raw_word)
                    else:
                        values = await self.reader.read_locked(
                            [
                                ReadableRegisters(
                                    field_obj.address, field_obj.size
                                )
                            ],
                        )

                        if not values or field not in values:
                            self.logger.warning(
                                "Write sent, but field %s could not be read back",
                                field,
                            )
                            return WriteVerificationResult(True, False)

                    actual_value = values.get(field)
                    verified = actual_value == value

                    self.logger.debug(
                        "Write verification result for %s: requested %r, "
                        "device reports %r",
                        field,
                        value,
                        actual_value,
                    )

                    if not verified:
                        self.logger.warning(
                            "Write read-back mismatch for %s: requested %r, "
                            "device reports %r",
                            field,
                            value,
                            actual_value,
                        )

                    return WriteVerificationResult(
                        write_succeeded=True,
                        readback_succeeded=True,
                        values=values,
                        verified=verified,
                    )

            except TimeoutError:
                self.logger.warning("Timeout during write or verification")
                return (
                    WriteVerificationResult(write_succeeded, False)
                    if verify
                    else False
                )
            except BleakError as err:
                self.logger.warning("Bleak error: %s", err)
                # Drop all per-connection state (standalone writer) so
                # the next write() reconnects, re-subscribes the
                # notifier and re-runs the encryption handshake.
                await self._mark_disconnected()
                return (
                    WriteVerificationResult(write_succeeded, False)
                    if verify
                    else False
                )
            except Exception as err:
                self.logger.warning("Error during write or verification: %s", err)
                return (
                    WriteVerificationResult(write_succeeded, False)
                    if verify
                    else False
                )
            finally:
                self._write_future = None

    def _calculate_expected_encrypted_length(
        self, buffer: bytearray
    ) -> int | None:
        if len(buffer) < 2:
            return None

        data_len = (buffer[0] << 8) + buffer[1]
        _, iv = self.encryption.getKeyIv()
        header_size = 2 if iv is not None else 6
        padded_len = (
            (data_len + AES_BLOCK_SIZE - 1) // AES_BLOCK_SIZE
        ) * AES_BLOCK_SIZE
        return header_size + padded_len

    async def _notification_handler(self, _: int, data: bytearray):
        message = Message(data)

        if message.is_pre_key_exchange:
            message.verify_checksum()

            if message.type == MessageType.CHALLENGE:
                response = self.encryption.msg_challenge(message)
                await self.client.write_gatt_char(WRITE_UUID, response)
            return

        if self.encryption.unsecure_aes_key is None:
            self.logger.error("Received encrypted message before key initialization")
            return

        self.encrypted_buffer.extend(data)
        expected_len = self._calculate_expected_encrypted_length(
            self.encrypted_buffer
        )
        if expected_len is None or len(self.encrypted_buffer) < expected_len:
            return

        complete_message = bytes(self.encrypted_buffer[:expected_len])
        self.encrypted_buffer = self.encrypted_buffer[expected_len:]
        key, iv = self.encryption.getKeyIv()

        try:
            decrypted = Message(self.encryption.aes_decrypt(complete_message, key, iv))
        except ValueError as err:
            self.logger.error("Decryption failed: %s", err)
            self.encrypted_buffer.clear()
            return

        if not decrypted.is_pre_key_exchange:
            # This is a regular response (e.g., write acknowledgment)
            if self._write_future and not self._write_future.done():
                self._write_future.set_result(decrypted.buffer)
            return

        decrypted.verify_checksum()
        if decrypted.type == MessageType.PEER_PUBKEY:
            response = self.encryption.msg_peer_pubkey(decrypted)
            await self.client.write_gatt_char(WRITE_UUID, response)
        elif decrypted.type == MessageType.PUBKEY_ACCEPTED:
            self.encryption.msg_key_accepted(decrypted)
            self.encryption_ready.set()
