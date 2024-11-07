import pymem
import ctypes
from ctypes import wintypes
import psutil

class LuaUnlocker:
    def __init__(self, process_name="Ascension.exe"):
        self.process_name = process_name

    def open_process(self, process_id):
        PROCESS_ALL_ACCESS = 0x001F0FFF
        return ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, process_id)

    def virtual_protect(self, process_handle, address, size, new_protect):
        old_protect = wintypes.DWORD()
        ctypes.windll.kernel32.VirtualProtectEx(
            process_handle, address, ctypes.c_size_t(size), new_protect, ctypes.byref(old_protect)
        )
        return old_protect.value

    def write_bytes(self, process_handle, address, data):
        size = len(data)
        buffer = (ctypes.c_char * size).from_buffer_copy(data)
        written = ctypes.c_size_t(0)
        ctypes.windll.kernel32.WriteProcessMemory(
            process_handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(written)
        )
        return written.value == size

    def unlock_lua_for_all_instances(self):
        try:
            # Get all processes with the name "Ascension.exe"
            for process in psutil.process_iter(['pid', 'name']):
                if process.info['name'] == self.process_name:
                    self.unlock_lua(process.info['pid'])
        except Exception as e:
            print(f"Error during unlocking all instances: {e}")

    def unlock_lua(self, process_id):
        try:
            # Open the process
            process_handle = self.open_process(process_id)
            if not process_handle:
                raise Exception("Could not open process. Try running as admin.")

            # Get base address for WoW
            pm = pymem.Pymem()
            pm.open_process_from_id(process_id)
            base_address = pymem.process.module_from_name(pm.process_handle, self.process_name).lpBaseOfDll

            # Unlock CastSpellByName
            cast_spell_by_name_address = base_address + 0x1191D2
            self.patch(process_handle, cast_spell_by_name_address, [0xEB])

            # Unlock TargetUnit
            target_unit_address = base_address + 0x124C76
            self.patch(process_handle, target_unit_address, [0xEB])

            # Unlock TargetNearestEnemy
            target_nearest_enemy_address = base_address + 0x124FD7
            self.patch(process_handle, target_nearest_enemy_address, [0x90, 0x90, 0x90, 0x90, 0x90, 0x90])

            # Unlock CancelShapeshiftForm
            cancel_shapeshift_address = base_address + 0x40319C
            self.patch(process_handle, cancel_shapeshift_address, [0xEB])

            # Other unlocks for 3.3.5a version
            additional_patches = [
                (base_address + 0x127F89, [0xEB]),
                (base_address + 0x11FF4A, [0xEB])
            ]

            for address, patch_data in additional_patches:
                self.patch(process_handle, address, patch_data)

            print(f"Lua unlock for WoW 3.3.5a completed successfully for PID {process_id}.")
        except Exception as e:
            print(f"Error during unlock for PID {process_id}: {e}")

    def patch(self, process_handle, address, new_data):
        # Change memory protection to PAGE_EXECUTE_READWRITE
        PAGE_EXECUTE_READWRITE = 0x40
        old_protect = self.virtual_protect(process_handle, address, len(new_data), PAGE_EXECUTE_READWRITE)

        # Write new bytes to the specified address
        if not self.write_bytes(process_handle, address, bytes(new_data)):
            raise Exception("Could not write data to process.")

        # Restore original memory protection
        self.virtual_protect(process_handle, address, len(new_data), old_protect)

if __name__ == "__main__":
    unlocker = LuaUnlocker(process_name="Ascension.exe")
    unlocker.unlock_lua_for_all_instances()
