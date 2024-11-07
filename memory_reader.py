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

    # Lua Interface
class LuaInterface:
        LuaState = 0x00D3F78C
        LuaLoadBuffer = 0x0084F860
        LuaPCall = 0x0084EC50
        LuaGetTop = 0x0084DBD0
        LuaSetTop = 0x0084DBF0
        LuaType = 0x0084DEB0
        LuaToNumber = 0x0084E030
        LuaToLString = 0x0084E0E0
        LuaToBoolean = 0x0084E0B0
        Lua_DoString = 0x00819210
        Lua_GetLocalizedText = 0x007225E0
        FrameScript_Execute = 0x00819210
        FrameScript_GetText = 0x00819D40

        def __init__(self, memory_reader):
            self.memory_reader = memory_reader
            self.process_handle = memory_reader.pm.process_handle
            self.lua_state = self._get_lua_state()
            self.Lua_DoString_func = ctypes.CFUNCTYPE(c_int, c_char_p, c_char_p, c_int)

        def _get_lua_state(self):
            """Retrieve the Lua state pointer."""
            return ctypes.c_void_p(self.memory_reader.read_uint(self.LuaState))

        def execute_lua_script(self, script):
            """Execute a Lua script using Lua_DoString."""
            script_address = self._allocate_string(script)
            # Cast the script_address to c_char_p to ensure it matches expected type
            script_address_str = ctypes.c_char_p(script_address)
            # Call using the correct function pointer
            result = self.Lua_DoString_func(script_address_str, script_address_str, 0)
            self._free_memory(script_address)
            return result



        def get_text(self, variable_name):
            """Retrieve a value from the Lua context."""
            var_address = self._allocate_string(variable_name)
            func = ctypes.CFUNCTYPE(c_char_p, c_char_p, c_int, c_int)(self.FrameScript_GetText)
            result = func(var_address, -1, 0)
            self._free_memory(var_address)
            return ctypes.string_at(result).decode('utf-8') if result else None

        def load_buffer(self, buffer):
            """Load a Lua buffer using LuaLoadBuffer."""
            buffer_address = self._allocate_string(buffer)
            func = ctypes.CFUNCTYPE(c_int, c_char_p, c_char_p, c_int)(self.LuaLoadBuffer)
            result = func(buffer_address, buffer_address, len(buffer))
            self._free_memory(buffer_address)
            return result

        def pcall(self, nargs, nresults, errfunc=0):
            """Calls LuaPCall to execute functions in Lua."""
            func = ctypes.CFUNCTYPE(c_int, c_int, c_int, c_int)(self.LuaPCall)
            return func(self.lua_state, nargs, nresults, errfunc)

        def get_top(self):
            """Gets the Lua stack's top index using LuaGetTop."""
            func = ctypes.CFUNCTYPE(c_int)(self.LuaGetTop)
            return func(self.lua_state)

        def set_top(self, index):
            """Sets the Lua stack's top index using LuaSetTop."""
            func = ctypes.CFUNCTYPE(None, c_int)(self.LuaSetTop)
            func(self.lua_state, index)

        def to_number(self, index):
            """Converts a Lua value to a number using LuaToNumber."""
            func = ctypes.CFUNCTYPE(c_double, c_int)(self.LuaToNumber)
            return func(self.lua_state, index)

        def to_lstring(self, index):
            """Converts a Lua value to a string using LuaToLString."""
            func = ctypes.CFUNCTYPE(c_char_p, c_int)(self.LuaToLString)
            result = func(self.lua_state, index)
            return ctypes.string_at(result).decode('utf-8') if result else None

        def to_boolean(self, index):
            """Converts a Lua value to a boolean using LuaToBoolean."""
            func = ctypes.CFUNCTYPE(c_bool, c_int)(self.LuaToBoolean)
            return func(self.lua_state, index)

        def _allocate_string(self, text):
            """Allocate memory and write a string to it for usage in Lua calls."""
            text_bytes = text.encode('utf-8') + b'\x00'
            address = ctypes.windll.kernel32.VirtualAllocEx(self.process_handle, 0, len(text_bytes), 0x3000, 0x40)
            ctypes.windll.kernel32.WriteProcessMemory(self.process_handle, address, text_bytes, len(text_bytes), None)
            return address

        def _free_memory(self, address):
            """Free allocated memory in the process."""
            ctypes.windll.kernel32.VirtualFreeEx(self.process_handle, address, 0, 0x8000)

    # Instantiate LuaInterface within WoWMemoryReader
        def get_lua_interface(self):
            return self.LuaInterface(self)
