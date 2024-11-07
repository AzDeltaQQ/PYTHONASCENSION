import pymem
import struct
import ctypes
from ctypes import c_int, c_char_p, c_void_p, c_bool, c_double
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WoWMemoryReader:

    def __init__(self, process_name="Ascension.exe"):
        self.pm = pymem.Pymem(process_name)
        self.base_address = pymem.process.module_from_name(self.pm.process_handle, process_name).lpBaseOfDll
        self.process_id = self.pm.process_id
        logging.info(f"Module Base Address for {process_name}: {hex(self.base_address)}")

    def read(self, address, size):
        """Reads raw bytes from memory at the specified address."""
        try:
            return self.pm.read_bytes(address, size)
        except pymem.exception.MemoryReadError as e:
            logging.error(f"Failed to read memory at {hex(address)}: {e}")
            return None

    def write(self, address, buffer):
        """Writes raw bytes to memory at the specified address."""
        if not address or not buffer:
            logging.error("Invalid address or buffer.")
            return False

        try:
            self.pm.write_bytes(address, buffer, len(buffer))
            return True
        except pymem.exception.MemoryWriteError as e:
            logging.error(f"Failed to write memory at {hex(address)}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error while writing memory at {hex(address)}: {e}")
            return False

    def write_uint(self, address, value):
        """Writes a 32-bit unsigned integer to memory."""
        if not address or value is None:
            logging.error("Invalid address or value for write_uint.")
            return False
        
        if not (0 <= value <= 0xFFFFFFFF):
            logging.error(f"Value {value} is out of range for a 32-bit unsigned integer.")
            return False

        try:
            buffer = struct.pack('I', value)
            self.write(address, buffer)
            logging.info(f"Wrote uint value {value} to address {hex(address)}")
            return True
        except Exception as e:
            logging.error(f"Failed to write uint at {hex(address)}: {e}")
            return False

    def write_uint64(self, address, value):
        """Writes a 64-bit unsigned integer to memory."""
        if not address or value is None:
            logging.error("Invalid address or value for write_uint64.")
            return False

        if not (0 <= value <= 0xFFFFFFFFFFFFFFFF):
            logging.error(f"Value {value} is out of range for a 64-bit unsigned integer.")
            return False

        try:
            buffer = struct.pack('Q', value)
            self.write(address, buffer)
            logging.info(f"Wrote uint64 value {value} to address {hex(address)}")
            return True
        except Exception as e:
            logging.error(f"Failed to write uint64 at {hex(address)}: {e}")
            return False

    def read_string(self, address, max_length=12):
        """Reads a string from memory, stopping at a null terminator or max_length."""
        raw_data = self.pm.read_bytes(address, max_length + 1)
        logging.info(f"Raw data read from address {hex(address)}: {raw_data}")
        
        name = ""
        for byte in raw_data:
            if byte == 0:  # Null terminator found
                break
            name += chr(byte)
        
        return name[:12]

    def read_byte(self, address):
        """Reads a single byte from memory."""
        data = self.read(address, 1)
        return struct.unpack('B', data)[0] if data else None

    def read_struct(self, address, struct_type):
        """Reads a structure from memory and returns it as an instance of struct_type."""
        data = self.read(address, ctypes.sizeof(struct_type))
        if data is None:
            return None
        return struct_type.from_buffer_copy(data)

    def read_uint64(self, address):
        """Reads a 64-bit unsigned integer from memory."""
        data = self.read(address, ctypes.sizeof(ctypes.c_uint64))
        return struct.unpack('Q', data)[0] if data else None

    def read_int64(self, address):
        """Reads a 64-bit signed integer from memory."""
        data = self.read(address, ctypes.sizeof(ctypes.c_int64))
        return struct.unpack('q', data)[0] if data else None

    def read_int32(self, address):
        """Reads a 32-bit signed integer from memory."""
        data = self.read(address, ctypes.sizeof(ctypes.c_int32))
        return struct.unpack('i', data)[0] if data else None

    def read_int(self, address):
        """Reads a 32-bit signed integer (common int) from memory."""
        data = self.read(address, ctypes.sizeof(ctypes.c_int))
        return struct.unpack('i', data)[0] if data else None

    def read_float(self, address):
        """Reads a 32-bit floating-point number from memory."""
        data = self.read(address, ctypes.sizeof(ctypes.c_float))
        return struct.unpack('f', data)[0] if data else None

    def read_pointer32(self, address):
        """Reads a 32-bit pointer (address) from memory and returns it as a c_void_p."""
        value = self.read_int32(address)
        return ctypes.c_void_p(value) if value is not None else None

    def read_uint(self, address):
        """Reads a 32-bit unsigned integer from memory."""
        data = self.read(address, ctypes.sizeof(ctypes.c_uint))
        return struct.unpack('I', data)[0] if data else None