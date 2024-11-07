import logging
import ctypes
import time
from typing import Optional, Tuple, List
from memory_reader import WoWMemoryReader  # Removed LuaInterface
from ctypes import c_int, c_void_p, c_bool
from offsets import Offsets
from lua import WoWLuaEngine

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Direct3D Offsets
class Direct3D9:
    pDevicePtr_1 = 0x00C5DF88
    pDevicePtr_2 = 0x397C
    oEndScene = 0xA8

# Function pointers and constants
CLIENT_DB_GET_LOCALIZED_ROW = 0x004CFD20
CLIENT_DB_GET_ROW = 0x0065C290
CREATE_PENDING_SPELL_CAST = 0x00805010

# Target flags
TARGET_FLAG_NONE = 0x00000000
TARGET_FLAG_UNIT = 0x00000002
TARGET_FLAG_ITEM = 0x00000010
TARGET_FLAG_CORPSE_ALLY = 0x00008000
TARGET_FLAG_UNIT_MINIPET = 0x00010000
TARGET_FLAG_UNIT_PASSENGER = 0x00100000
TARGET_FLAG_GAMEOBJECT = 0x00000800

class Spell:
    """Defines a spell with an ID and healing percentage."""
    def __init__(self, spell_id):
        self.id = spell_id

    def __str__(self):
        return f"Spell(ID: {self.id})"

class SpellCollection:
    def __init__(self, memory_reader):
        self.pm = memory_reader
        self.known_spells = []
        self.update = True
        self.cast_spell_delegate = None
        self.initialize_delegates()

    def initialize_delegates(self):
        try:
            # Get the correct function address
            cast_spell_addr = Offsets.LuaFuncs["lua_CastSpellByID"]
            
            # Define correct function prototype
            # __stdcall convention, void return type, takes spell ID and optionally target GUID
            SPELL_FUNC = ctypes.WINFUNCTYPE(
                None,            # Return type (void)
                ctypes.c_uint32, # Spell ID
                ctypes.c_char_p  # Target GUID (optional)
            )
            
            # Create delegate
            self.cast_spell_delegate = SPELL_FUNC(cast_spell_addr)
            logging.info(f"Spell casting delegate initialized at {hex(cast_spell_addr)}")
            
        except Exception as e:
            logging.error(f"Failed to initialize spell delegates: {e}")
            raise
    
    def cast_spell(self, spell_id: int, target_guid: str = None) -> bool:
        try:
            if self.cast_spell_delegate is None:
                logging.error("Spell delegate not initialized")
                return False
    
            # Convert spell_id to unsigned 32-bit int
            spell_id = ctypes.c_uint32(spell_id)
            
            # Convert target GUID if provided
            target = ctypes.c_char_p(target_guid.encode()) if target_guid else ctypes.c_char_p(None)
            
            # Call the function
            self.cast_spell_delegate(spell_id, target)
            logging.info(f"Cast spell {spell_id.value} {f'on {target_guid}' if target_guid else ''}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to cast spell {spell_id}: {e}")
            return False


    def register_delegate(self, address, func_type):
        try:
            return func_type(address)
        except Exception as e:
            logging.error(f"Failed to register delegate at {hex(address)}: {e}")
            raise

    def update_known_spells(self):
        if not self.is_in_game() or not self.update:
            return
        try:
            spell_count = self.pm.read_int(Offsets.Spell.SpellCount)
            if spell_count <= 0:
                logging.warning("No spells found in spellbook")
                return
            
            known_spells = []
            for i in range(spell_count):
                spell_id = self.pm.read_uint(Offsets.Spell.SpellBook + (i * 4))
                known_spells.append(Spell(spell_id))
                logging.info(f"Added Spell: ID {spell_id}")
                
            if known_spells:
                self.known_spells = known_spells
                logging.info(f"SpellBook: {len(self.known_spells)} spells loaded")
            self.update = False
        except Exception as e:
            logging.warning(f"Failed to update known spells: {e}")

    def is_spell_ready(self, spell_id):
        try:
            cooldown_list = self.pm.read_uint(self.pm.base_address + 
                          Offsets.Globals.SpellCooldownPtr - 0x400000 + 0x8)
            frequency = time.perf_counter() * 1000
            
            while cooldown_list != 0 and (cooldown_list & 1) == 0:
                spell_cooldown_id = self.pm.read_uint(cooldown_list + 0x8)
                if spell_cooldown_id == spell_id:
                    start_time = self.pm.read_uint(cooldown_list + 0x10)
                    cooldown_duration = max(
                        self.pm.read_int(cooldown_list + 0x14),
                        self.pm.read_int(cooldown_list + 0x20)
                    )
                    if (start_time + cooldown_duration) > frequency:
                        return False
                cooldown_list = self.pm.read_uint(cooldown_list + 4)
        except Exception:
            return False
        return True

    def is_in_game(self):
        return True

    def has_spell(self, spell_identifier):
        if isinstance(spell_identifier, int):
            return any(spell.id == spell_identifier for spell in self.known_spells)
        logging.error("Spell identifier must be an int (spell ID)")
        return False

    def __getitem__(self, key):
        if isinstance(key, int):
            return next((spell for spell in self.known_spells if spell.id == key), None)
        logging.error("Key must be an int (spell ID)")
        return None

class D3DHook:
    """Handles Direct3D hooking for spell casting in the main thread."""
    def __init__(self, memory_reader: WoWMemoryReader, spell_caster) -> None:
        self.memory_reader = memory_reader
        self.spell_caster = spell_caster
        self.device_pointer = self.get_device_pointer()
        self.original_end_scene = None
        self.hooked_end_scene = None
        self.spell_cast_queue: List[Tuple[int, int]] = []
        self.last_cast_time = 0

    def get_device_pointer(self) -> Optional[int]:
        try:
            pDeviceBase = self.memory_reader.read_uint(Direct3D9.pDevicePtr_1)
            if not pDeviceBase:
                logging.error("Failed to read base device pointer")
                return None
            return pDeviceBase
        except Exception as e:
            logging.error(f"Error reading device pointer: {e}")
            return None

    def hook_end_scene(self) -> None:
        if not self.device_pointer:
            logging.error("Direct3D device pointer is not initialized")
            return

        end_scene_address = self.memory_reader.read_uint(
            self.device_pointer + Direct3D9.oEndScene
        )
        logging.info(f"Original EndScene address: {hex(end_scene_address)}")

        self.original_end_scene = ctypes.cast(
            end_scene_address, 
            ctypes.CFUNCTYPE(ctypes.c_int)
        )

        @ctypes.CFUNCTYPE(ctypes.c_int)
        def hooked_end_scene():
            current_time = time.time()
            if current_time - self.last_cast_time >= 2.0:
                try:
                    self.spell_caster.Spell_C_Cast_Delegate(1082, 0)
                    self.last_cast_time = current_time
                    logging.info("Test spell 1082 cast attempted")
                except Exception as e:
                    logging.error(f"Failed to cast test spell: {e}")
            return self.original_end_scene()

        self.hooked_end_scene = hooked_end_scene
        self.memory_reader.write_uint64(
            self.device_pointer + Direct3D9.oEndScene,
            ctypes.cast(self.hooked_end_scene, ctypes.c_void_p).value
        )
        logging.info("EndScene hooked successfully with test spell casting")

    def unhook_end_scene(self) -> None:
        if self.original_end_scene and self.device_pointer:
            self.memory_reader.write_uint64(
                self.device_pointer + Direct3D9.oEndScene,
                ctypes.cast(self.original_end_scene, ctypes.c_void_p).value
            )
            logging.info("EndScene unhooked successfully")

    def queue_spell_cast(self, spell_id: int, target: int) -> None:
        self.spell_cast_queue.append((spell_id, target))
        logging.info(f"Queued spell cast for ID {spell_id} on target {target}")

    def execute_main_thread_functions(self) -> None:
        while self.spell_cast_queue:
            spell_id, target = self.spell_cast_queue.pop(0)
            logging.info(f"Executing spell cast for ID {spell_id} on target {target}")
            self.spell_caster.Spell_C_Cast_Delegate(spell_id, target)