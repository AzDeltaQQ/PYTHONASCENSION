from typing import Any, Optional, Callable
import ctypes
from enum import IntEnum

class LuaType(IntEnum):
    """Lua value types"""
    LUA_TNIL = 0
    LUA_TBOOLEAN = 1 
    LUA_TLIGHTUSERDATA = 2
    LUA_TNUMBER = 3
    LUA_TSTRING = 4
    LUA_TTABLE = 5
    LUA_TFUNCTION = 6
    LUA_TUSERDATA = 7
    LUA_TTHREAD = 8

class LuaInterface:
    """Memory addresses for Lua functions"""
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
    Lua_SetTop = 0x000084DBF0
    FrameScript__PushString = 0x0084E350
    FrameScript_pushinteger = 0x0084E2D0
    FrameScript_pushboolean = 0x0084E4D0
    FrameScript_RegisterFunction = 0x004181B0
    FrameScript_UnregisterFunction = 0x00817FD0
    FrameScript_SignalEvent = 0x0081AC90

class LuaState:
    """Wrapper for Lua state pointer and core functions"""
    
    def __init__(self) -> None:
        self.L = ctypes.c_void_p(LuaInterface.LuaState)

    def lua_gettop(self) -> int:
        return ctypes.cast(
            LuaInterface.LuaGetTop,
            ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)
        )(self.L)

    def lua_settop(self, index: int) -> None:
        ctypes.cast(
            LuaInterface.LuaSetTop,
            ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int)
        )(self.L, index)

    def lua_pushstring(self, s: str) -> None:
        ctypes.cast(
            LuaInterface.FrameScript__PushString,
            ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_char_p)
        )(self.L, s.encode('utf-8'))

    def lua_pcall(self, nargs: int, nresults: int, errfunc: int) -> int:
        return ctypes.cast(
            LuaInterface.LuaPCall,
            ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int)
        )(self.L, nargs, nresults, errfunc)

    def lua_type(self, index: int) -> int:
        return ctypes.cast(
            LuaInterface.LuaType,
            ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int)
        )(self.L, index)

    def lua_tonumber(self, index: int) -> float:
        return ctypes.cast(
            LuaInterface.LuaToNumber,
            ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p, ctypes.c_int)
        )(self.L, index)

    def lua_tostring(self, index: int) -> str:
        length = ctypes.c_size_t()
        ptr = ctypes.cast(
            LuaInterface.LuaToLString,
            ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t))
        )(self.L, index, ctypes.byref(length))
        return ptr[:length.value].decode('utf-8')

    def lua_toboolean(self, index: int) -> bool:
        return bool(ctypes.cast(
            LuaInterface.LuaToBoolean,
            ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int)
        )(self.L, index))

class LuaHelpers:
    """Helper functions for Lua value conversion"""

    @staticmethod
    def push_value(L: LuaState, val: Any) -> None:
        if isinstance(val, str):
            L.lua_pushstring(val)
        elif isinstance(val, int):
            ctypes.cast(
                LuaInterface.FrameScript_pushinteger,
                ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int)
            )(L.L, val)
        elif isinstance(val, bool):
            ctypes.cast(
                LuaInterface.FrameScript_pushboolean,
                ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int)
            )(L.L, int(val))
        elif val is None:
            L.lua_settop(L.lua_gettop() + 1)  # Push nil
        else:
            raise ValueError(f"Unsupported type: {type(val)}")

    @staticmethod
    def get_value(L: LuaState, index: int) -> Any:
        lua_type = L.lua_type(index)
        if lua_type == LuaType.LUA_TNIL:
            return None
        elif lua_type == LuaType.LUA_TBOOLEAN:
            return L.lua_toboolean(index)
        elif lua_type == LuaType.LUA_TNUMBER:
            return L.lua_tonumber(index)
        elif lua_type == LuaType.LUA_TSTRING:
            return L.lua_tostring(index)
        else:
            raise ValueError(f"Unsupported Lua type: {lua_type}")

    @staticmethod
    def do_string(L: LuaState, code: str) -> Any:
        ctypes.cast(
            LuaInterface.Lua_DoString,
            ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p)
        )(L.L, code.encode('utf-8'), b"LuaHelpers.do_string")
        return LuaHelpers.get_value(L, -1)

class WoWLuaEngine:
    """Main interface for WoW Lua execution"""

    def __init__(self) -> None:
        self.lua_state = LuaState()

    def execute_lua(self, code: str) -> Any:
        """Execute Lua code and return the result"""
        return LuaHelpers.do_string(self.lua_state, code)

    def get_localized_text(self, text_id: str) -> Optional[str]:
        """Get localized text by ID"""
        ctypes.cast(
            LuaInterface.Lua_GetLocalizedText,
            ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p)
        )(self.lua_state.L, text_id.encode('utf-8'))
        return LuaHelpers.get_value(self.lua_state, -1)

    def register_function(self, func_name: str, py_func: Callable) -> None:
        """Register a Python function to be called from Lua"""
        def lua_wrapper(L: Any) -> int:
            try:
                args = [LuaHelpers.get_value(self.lua_state, i) 
                       for i in range(1, self.lua_state.lua_gettop() + 1)]
                result = py_func(*args)
                LuaHelpers.push_value(self.lua_state, result)
                return 1
            except Exception as e:
                print(f"Error in Lua wrapper: {e}")
                return 0

        c_func = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)(lua_wrapper)
        ctypes.cast(
            LuaInterface.FrameScript_RegisterFunction,
            ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p)
        )(self.lua_state.L, func_name.encode('utf-8'), c_func)

    def unregister_function(self, func_name: str) -> None:
        """Unregister a previously registered function"""
        ctypes.cast(
            LuaInterface.FrameScript_UnregisterFunction,
            ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_char_p)
        )(self.lua_state.L, func_name.encode('utf-8'))

    def signal_event(self, event_name: str, *args: Any) -> None:
        """Signal a WoW event with optional arguments"""
        ctypes.cast(
            LuaInterface.FrameScript_SignalEvent,
            ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_char_p)
        )(self.lua_state.L, event_name.encode('utf-8'))
        for arg in args:
            LuaHelpers.push_value(self.lua_state, arg)
        self.lua_state.lua_pcall(len(args), 0, 0)