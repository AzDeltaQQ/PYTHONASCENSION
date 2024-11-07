import logging
import ctypes
from ctypes import c_void_p
from memory_reader import WoWMemoryReader

# Offsets for Direct3D functions
class Direct3D9:
    pDevicePtr_1 = 0x00C5DF88
    pDevicePtr_2 = 0x397C
    oEndScene = 0xA8

class D3DHook:
    def __init__(self, memory_reader, spell_caster):
        self.memory_reader = memory_reader
        self.spell_caster = spell_caster
        self.device_pointer = self.get_device_pointer()
        self.original_end_scene = None
        self.hooked_end_scene = None
        self.spell_cast_queue = []

    def get_device_pointer(self):
        try:
            pDeviceBase = self.memory_reader.read_uint(Direct3D9.pDevicePtr_1)
            if not pDeviceBase:
                logging.error("Failed to read base device pointer.")
                return None
            return pDeviceBase
        except Exception as e:
            logging.error(f"Error reading device pointer: {e}")
            return None

    def hook_end_scene(self):
        """Hooks the EndScene function of the Direct3D device."""
        if not self.device_pointer:
            logging.error("Direct3D device pointer is not initialized.")
            return

        end_scene_address = self.memory_reader.read_uint(self.device_pointer + Direct3D9.oEndScene)
        logging.info(f"Original EndScene function address: {hex(end_scene_address)}")

        self.original_end_scene = ctypes.cast(end_scene_address, ctypes.CFUNCTYPE(ctypes.c_int))

        @ctypes.CFUNCTYPE(ctypes.c_int)
        def hooked_end_scene():
            logging.info("Hooked EndScene function called!")
            result = self.original_end_scene()
            self.execute_main_thread_functions()
            return result

        self.hooked_end_scene = hooked_end_scene
        self.memory_reader.write_uint64(self.device_pointer + Direct3D9.oEndScene, ctypes.cast(self.hooked_end_scene, ctypes.c_void_p).value)
        logging.info("EndScene function hooked successfully.")

    def unhook_end_scene(self):
        """Unhooks the EndScene function, restoring the original."""
        if self.original_end_scene and self.device_pointer:
            self.memory_reader.write_uint64(self.device_pointer + Direct3D9.oEndScene, ctypes.cast(self.original_end_scene, ctypes.c_void_p).value)
            logging.info("EndScene function unhooked successfully.")

    def queue_spell_cast(self, spell_id, target):
        """Add a spell cast request to the queue."""
        self.spell_cast_queue.append((spell_id, target))
        logging.info(f"Queued spell cast for ID {spell_id} on target {target}")

    def execute_main_thread_functions(self):
        """Execute queued spell casts on the main thread."""
        while self.spell_cast_queue:
            spell_id, target = self.spell_cast_queue.pop(0)
            logging.info(f"Executing spell cast for ID {spell_id} on target {target}")
            self.spell_caster.Spell_C_Cast_Delegate(spell_id, target)