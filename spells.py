import ctypes
import time
import logging
from offsets import Offsets
import pymem

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Spell:
    """Defines a spell with an ID and healing percentage."""
    def __init__(self, spell_id, healing_percentage=0):
        self.id = spell_id
        self.healing_percentage = healing_percentage  # Used for prioritizing healing spells

    def __str__(self):
        return f"Spell(ID: {self.id}, Healing Percentage: {self.healing_percentage})"


class SpellCollection:
    """Manages a collection of spells and delegates for spellcasting."""
    def __init__(self, memory_reader):
        self.pm = memory_reader
        self.known_spells = []
        self.update = True
        self.get_spell_cooldown_delegate = None
        self.initialize_delegates()

    def initialize_delegates(self):
        """Registers the casting and cooldown functions."""
        try:
            # Initialize GetSpellCooldown function delegate
            self.get_spell_cooldown_delegate = self.register_delegate(
                Offsets.Spell.GetSpellCooldown,
                ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_bool), ctypes.POINTER(ctypes.c_int))
            )
        except Exception as e:
            logging.error(f"Failed to initialize spell function delegates: {e}")
            raise

    def register_delegate(self, address, func_type):
        """Registers a function delegate at a given address."""
        try:
            return func_type(address)
        except Exception as e:
            logging.error(f"Failed to register delegate at address {hex(address)}: {e}")
            raise

    def update_known_spells(self):
        """Loads known spells from the spellbook."""
        if not self.is_in_game() or not self.update:
            return

        try:
            spell_count = self.pm.read_int(Offsets.Spell.SpellCount)
            if spell_count <= 0:
                logging.warning("No spells found in the spellbook.")
                return

            known_spells = []

            # Iterate over spellbook and add spells to known_spells list
            for i in range(spell_count):
                spell_id = self.pm.read_uint(Offsets.Spell.SpellBook + (i * 4))
                known_spells.append(Spell(spell_id))
                logging.info(f"Added Spell: ID {spell_id}")

            # Update known spells if any were found
            if len(known_spells) > 0:
                self.known_spells = known_spells
                logging.info(f"SpellBook: {len(self.known_spells)} spells loaded.")
            else:
                logging.info("No valid spells loaded.")

            self.update = False
        except Exception as e:
            logging.warning(f"Failed to update known spells: {e}")

    def has_spell(self, spell_identifier):
        """Checks if the player has a specific spell by ID."""
        if isinstance(spell_identifier, int):
            return any(spell.id == spell_identifier for spell in self.known_spells)
        else:
            logging.error("Spell identifier must be an int (spell ID).")
            return False

    def is_in_game(self):
        """Placeholder for checking if the player is in-game."""
        return True

    def is_spell_ready(self, spell_id):
        """Checks if a spell is ready to cast, factoring in cooldown."""
        try:
            cooldown_list = self.pm.read_uint(self.pm.base_address + Offsets.Globals.SpellCooldownPtr - 0x400000 + 0x8)
            frequency = time.perf_counter() * 1000  # Frequency in milliseconds

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
        except pymem.exception.MemoryReadError:
            return False

        return True

    def __getitem__(self, key):
        """Retrieves a spell by ID."""
        if isinstance(key, int):
            return next((spell for spell in self.known_spells if spell.id == key), None)
        else:
            logging.error("Key must be an int (spell ID).")
            return None
