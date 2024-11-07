# TESTSPELLCAST.PY
from memory_reader import WoWMemoryReader
from spellsystem import SpellCollection
import logging
import ctypes
import time

def test_spell_casting():
    try:
        # Set up detailed logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Initialize with process validation
        memory_reader = WoWMemoryReader("Ascension.exe")
        if not memory_reader.pm.process_handle:
            logging.error("Failed to get process handle")
            return
            
        spell_collection = SpellCollection(memory_reader)

        # Test with known spell ID (Caster Tax)
        test_spell_id = 1082
        
        # Validate game state
        if not spell_collection.is_in_game():
            logging.error("Not in game - cannot test spell casting")
            return

        logging.info(f"Testing spell cast for ID: {test_spell_id}")
        
        # Update and verify spell knowledge
        spell_collection.update_known_spells()
        
        if not spell_collection.has_spell(test_spell_id):
            logging.error(f"Spell {test_spell_id} not found in spellbook")
            return

        # Validate spell is ready
        if not spell_collection.is_spell_ready(test_spell_id):
            logging.info(f"Spell {test_spell_id} is on cooldown")
            return

        # Add small delay before cast
        time.sleep(0.1)
        
        # Attempt cast with memory protection
        result = spell_collection.cast_spell(test_spell_id)
        
        if result:
            logging.info(f"Successfully cast spell {test_spell_id}")
        else:
            logging.error(f"Failed to cast spell {test_spell_id}")

    except Exception as e:
        logging.error(f"Test failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    test_spell_casting()