import logging
import ctypes
from ctypes import c_int, c_void_p, c_bool
from memory_reader import WoWMemoryReader
from spells import SpellCollection
from memory_reader import LuaInterface  # Assuming LuaInterface is implemented and available
from d3dhook import D3DHook  # Import D3DHook from d3dhook.py

# Define the function pointers
CLIENT_DB_GET_LOCALIZED_ROW = 0x004CFD20
CLIENT_DB_GET_ROW = 0x0065C290
CREATE_PENDING_SPELL_CAST = 0x00805010

# Define target flags
TARGET_FLAG_NONE = 0x00000000
TARGET_FLAG_UNIT = 0x00000002
TARGET_FLAG_ITEM = 0x00000010
TARGET_FLAG_SOURCE_LOCATION = 0x00000020
TARGET_FLAG_DEST_LOCATION = 0x00000040
TARGET_FLAG_UNIT_ENEMY = 0x00000080
TARGET_FLAG_UNIT_ALLY = 0x00000100
TARGET_FLAG_CORPSE_ENEMY = 0x00000200
TARGET_FLAG_UNIT_DEAD = 0x00000400
TARGET_FLAG_GAMEOBJECT = 0x00000800
TARGET_FLAG_TRADE_ITEM = 0x00001000
TARGET_FLAG_STRING = 0x00002000
TARGET_FLAG_CORPSE_ALLY = 0x00008000
TARGET_FLAG_UNIT_MINIPET = 0x00010000
TARGET_FLAG_DEST_TARGET = 0x00040000
TARGET_FLAG_UNIT_PASSENGER = 0x00100000

class ObjectGuid:
    """Represents target type checks based on GUID attributes."""

    def __init__(self, guid):
        self.guid = guid

    def IsDead(self):
        """Check if the target is dead."""
        return self.guid.get('status') == 'dead'

    def IsUnit(self):
        """Check if the target is a unit."""
        return self.guid.get('type') == 'unit'

    def IsGameObject(self):
        """Check if the target is a game object."""
        return self.guid.get('type') == 'gameobject'

    def IsEnemyCorpse(self):
        """Check if the target is an enemy corpse."""
        return self.guid.get('type') == 'corpse' and self.guid.get('alignment') == 'enemy'

    def IsAllyCorpse(self):
        """Check if the target is an ally corpse."""
        return self.guid.get('type') == 'corpse' and self.guid.get('alignment') == 'ally'

    def IsMiniPet(self):
        """Check if the target is a mini pet."""
        return self.guid.get('type') == 'minipet'

    def IsPassenger(self):
        """Check if the target is a passenger."""
        return self.guid.get('type') == 'passenger'


class SpellCastTargets:
    """Represents the spell casting targets and target validation."""
    def __init__(self, target_mask=0, object_target=None, item_target=None, object_target_guid=None):
        self.m_targetMask = target_mask
        self.m_objectTarget = object_target
        self.m_itemTarget = item_target
        self.m_objectTargetGUID = object_target_guid

    def IsValidTarget(self):
        """Validates the target based on the target mask and GUID type."""
        
        # Validate object target based on the target flags
        if self.m_targetMask & TARGET_FLAG_UNIT and (not self.m_objectTargetGUID or not self.m_objectTargetGUID.IsUnit()):
            logging.error("Expected a unit target, but GUID or target is invalid.")
            return False
        if self.m_targetMask & TARGET_FLAG_CORPSE_ALLY and (not self.m_objectTargetGUID or not self.m_objectTargetGUID.IsAllyCorpse()):
            logging.error("Expected an ally corpse target, but GUID is invalid.")
            return False
        if self.m_targetMask & TARGET_FLAG_GAMEOBJECT and (not self.m_objectTargetGUID or not self.m_objectTargetGUID.IsGameObject()):
            logging.error("Expected a game object target, but GUID is invalid.")
            return False
        if self.m_targetMask & TARGET_FLAG_CORPSE_ENEMY and (not self.m_objectTargetGUID or not self.m_objectTargetGUID.IsEnemyCorpse()):
            logging.error("Expected an enemy corpse target, but GUID is invalid.")
            return False

        # Validate item target
        if self.m_targetMask & TARGET_FLAG_ITEM and not self.m_itemTarget:
            logging.error("Expected an item target, but target is missing.")
            return False

        # Additional validations for specific cases
        if self.m_targetMask & TARGET_FLAG_UNIT_MINIPET and (not self.m_objectTargetGUID or not self.m_objectTargetGUID.IsMiniPet()):
            logging.error("Expected a mini pet target, but GUID is invalid.")
            return False
        if self.m_targetMask & TARGET_FLAG_UNIT_PASSENGER and (not self.m_objectTargetGUID or not self.m_objectTargetGUID.IsPassenger()):
            logging.error("Expected a passenger target, but GUID is invalid.")
            return False
        if self.m_targetMask & TARGET_FLAG_UNIT_DEAD and (not self.m_objectTargetGUID or not self.m_objectTargetGUID.IsDead()):
            logging.error("Expected a dead unit target, but target is not dead.")
            return False

        return True

class SpellCaster:
    def __init__(self, memory_reader: WoWMemoryReader, spell_collection: SpellCollection):
        self.memory_reader = memory_reader
        self.spell_collection = spell_collection
        self.lua = LuaInterface(memory_reader)  # Assuming Lua interface is initialized here
        self.Spell_C_Cast_Delegate = None
        self.d3d_hook = D3DHook(memory_reader, self)
        self.initialize_delegates()
        self.d3d_hook.hook_end_scene()

    def initialize_delegates(self):
        try:
            Spell_C_Cast_Address = 0x0053E060
            logging.info(f"Initializing Lua_CastSpellByID delegate at address: {hex(Spell_C_Cast_Address)}")
            self.Spell_C_Cast_Delegate = self.register_delegate(
                Spell_C_Cast_Address,
                ctypes.CFUNCTYPE(None, c_int, c_int)
            )
            if not self.Spell_C_Cast_Delegate:
                logging.error("Failed to initialize Lua_CastSpellByID delegate.")

            # Initialize other delegates
            self.GetRow_Delegate = self.register_delegate(CLIENT_DB_GET_ROW, ctypes.CFUNCTYPE(c_void_p, c_int))
            self.GetLocalizedRow_Delegate = self.register_delegate(CLIENT_DB_GET_LOCALIZED_ROW, ctypes.CFUNCTYPE(c_void_p, c_int))
            self.CreatePendingSpellCast_Delegate = self.register_delegate(CREATE_PENDING_SPELL_CAST, ctypes.CFUNCTYPE(c_void_p, c_int, c_int, c_int, c_int))

        except Exception as e:
            logging.error(f"Error initializing delegates: {e}")

    def register_delegate(self, address, cfunc_type):
        """Registers a delegate for a given address."""
        try:
            logging.info(f"Creating function delegate at address: {hex(address)}")
            func_pointer = ctypes.cast(address, ctypes.c_void_p).value
            return cfunc_type(func_pointer)
        except Exception as e:
            logging.error(f"Failed to register delegate at address {hex(address)}: {e}")
            return None

    def Spell_C_CastSpell(self, spellId, caster, objectGuid, spellAttributes):
        """Casts a spell, with validation and handling logic for attributes."""
        
        # Step 1: Check if the spell exists in the database
        spellRecord = self.GetRow_Delegate(spellId)
        if not spellRecord:
            logging.error("Spell not found in database")
            return False

        # Step 2: Retrieve and validate localized spell data
        localizedRow = self.GetLocalizedRow_Delegate(spellId)
        if not localizedRow:  # Fixed syntax error here
            logging.error("Localized data restriction or localization issue")
            return False

        # Step 3: Initialize the SpellCast object with the required parameters
        spellCast = self.CreatePendingSpellCast_Delegate(spellId, caster, objectGuid, spellAttributes)
        if not spellCast:
            logging.error("Failed to initialize SpellCast")
            return False

        # Step 4: Validate the target, if provided
        spell_targets = SpellCastTargets(target_mask=spellAttributes, object_target=objectGuid, object_target_guid=objectGuid)
        if objectGuid and not spell_targets.IsValidTarget():
            logging.error("Invalid target GUID")
            return False

        # Step 5: Handle specific conditions based on spell attributes
        # if spellRecord.HasShapeshiftFlag():
        #     pass
        # if spellRecord.attributesEx & SPELL_ATTR_SPECIAL:
        #     pass

        # Step 6: Attempt to execute the spell cast
        # if not SpellCast.Execute(spellCast):
        #     Spell_C_SpellFailed(spellId, caster, objectGuid, SPELL_ERROR_INVALID_CONDITIONS)
        #     logging.error("Spell execution failed due to invalid conditions")
        #     return False

        logging.info("Spell cast successfully")
        return True


class SpellCollection:
    def __init__(self, memory_reader: WoWMemoryReader):
        self.memory_reader = memory_reader
        self.is_valid_spell_delegate = None
        self.initialize_is_valid_spell_delegate()

    def initialize_is_valid_spell_delegate(self):
        try:
            is_valid_spell_address = 0x00540650
            logging.info(f"Initializing is_valid_spell delegate at address: {hex(is_valid_spell_address)}")
            self.is_valid_spell_delegate = ctypes.CFUNCTYPE(c_bool, c_int)(is_valid_spell_address)
            if not self.is_valid_spell_delegate:
                logging.error("Failed to initialize is_valid_spell delegate.")
        except Exception as e:
            logging.error(f"Failed to initialize is_valid_spell delegate: {e}")

    def is_valid_spell(self, spell_id):
        try:
            if not self.is_valid_spell_delegate:
                logging.error("is_valid_spell delegate is not initialized.")
                return False
            result = self.is_valid_spell_delegate(spell_id)
            logging.info(f"Spell ID {spell_id} validity check: {result}")
            return result
        except Exception as e:
            logging.error(f"Error in is_valid_spell: {e}")
            return False