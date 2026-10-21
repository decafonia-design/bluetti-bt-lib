import struct

from . import DeviceRegister, RegisterAction


class WriteableRegister(DeviceRegister):
    def __init__(self, address: int, value: int):
        super().__init__(RegisterAction.WRITE, struct.pack("!HH", address, value))
        self.address = address
        self.value = value

    def response_size(self):
        return 8

    def is_valid_response(self, response: bytes) -> bool:
        """Function 06 answers by echoing the request (slave, function, address, value)"""
        return (
            len(response) == 8
            and response[:6] == bytes(self.cmd[:6])
            and super().is_valid_response(response)
        )

    def parse_response(self, response: bytes):
        return bytes(response[4:6])

    def __repr__(self):
        return f"WriteableRegister(address={self.address}, value={self.value:#04x})"
