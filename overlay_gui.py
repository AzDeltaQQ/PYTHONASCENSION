import tkinter as tk
from tkinter import ttk
import logging
from player_scan import PlayerScan
from memory_reader import WoWMemoryReader
from spellsystem import SpellCollection, D3DHook  # Updated import
import queue


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class OverlayGUI:
    def __init__(self, master, player_scan, spell_collection, d3d_hook):
        self.master = master
        self.master.title("Overlay GUI")
        self.player_scan = player_scan
        self.memory_reader = player_scan.pm 
        self.spell_collection = spell_collection # Use the passed-in spell_collection
        self.d3d_hook = d3d_hook
        self.spell_collection.update_known_spells()
        self.spell_cast_queue = queue.Queue()
        self.create_tabs()
        self.update_gui()
        self.process_queue()

    def create_tabs(self):
        self.tab_control = ttk.Notebook(self.master)

        # Player Info Tab
        self.player_info_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.player_info_tab, text="Player Info")
        self.create_player_info_tab()

        # Party Info Tab
        self.party_info_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.party_info_tab, text="Party Info")
        self.create_party_info_tab()

        # Object Manager Tab
        self.object_manager_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.object_manager_tab, text="Object Manager")
        self.create_object_manager_tab()

        # Known Spells Tab
        self.spells_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.spells_tab, text="Known Spells")
        self.create_spells_tab()

        self.tab_control.pack(expand=1, fill='both')

    def create_player_info_tab(self):
        self.player_name_label = ttk.Label(self.player_info_tab, text="Player Name:")
        self.player_name_label.grid(row=0, column=0)

        self.health_label = ttk.Label(self.player_info_tab, text="Health:")
        self.health_label.grid(row=1, column=0)

        self.mana_label = ttk.Label(self.player_info_tab, text="Mana:")
        self.mana_label.grid(row=2, column=0)

    def create_party_info_tab(self):
        self.party_info_label = ttk.Label(self.party_info_tab, text="Party Members Info")
        self.party_info_label.grid(row=0, column=0)

        self.party_members_tree = ttk.Treeview(self.party_info_tab, columns=('Name', 'Current Health', 'Max Health'), show='headings')
        self.party_members_tree.heading('Name', text='Name')
        self.party_members_tree.heading('Current Health', text='Current Health')
        self.party_members_tree.heading('Max Health', text='Max Health')
        self.party_members_tree.grid(row=1, column=0, sticky='nsew')

        self.party_info_tab.grid_rowconfigure(1, weight=1)
        self.party_info_tab.grid_columnconfigure(0, weight=1)

    def create_object_manager_tab(self):
        self.object_manager_label = ttk.Label(self.object_manager_tab, text="Object Manager Info")
        self.object_manager_label.grid(row=0, column=0)

        self.object_manager_tree = ttk.Treeview(self.object_manager_tab, columns=('GUID', 'Type'), show='headings')
        self.object_manager_tree.heading('GUID', text='GUID')
        self.object_manager_tree.heading('Type', text='Type')
        self.object_manager_tree.grid(row=1, column=0, sticky='nsew')

        self.object_manager_tab.grid_rowconfigure(1, weight=1)
        self.object_manager_tab.grid_columnconfigure(0, weight=1)

    def create_spells_tab(self):
        """Create a tab to display known spells."""
        self.spells_label = ttk.Label(self.spells_tab, text="Known Spells")
        self.spells_label.grid(row=0, column=0)

        self.spells_tree = ttk.Treeview(self.spells_tab, columns=('ID', 'Healing Percentage'), show='headings')
        self.spells_tree.heading('ID', text='Spell ID')
        self.spells_tree.heading('Healing Percentage', text='Healing Percentage')
        self.spells_tree.grid(row=1, column=0, sticky='nsew')

        self.spells_tab.grid_rowconfigure(1, weight=1)
        self.spells_tab.grid_columnconfigure(0, weight=1)

        # Populate the spells tree with known spells
        self.update_spells_tab()

    def update_gui(self):
        """Periodically updates the GUI with the latest player and party info."""
        self.update_player_info()
        self.update_party_info()
        self.master.after(1000, self.update_gui)  # Update every second

    def update_player_info(self):
        player_name = self.player_scan.get_local_player_name()
        health, max_health, mana, max_mana = self.player_scan.get_local_player_health_mana()

        self.player_name_label.config(text=f"Player Name: {player_name}")
        self.health_label.config(text=f"Health: {health}/{max_health}")
        self.mana_label.config(text=f"Mana: {mana}/{max_mana}")

    def update_party_info(self):
        self.party_members_tree.delete(*self.party_members_tree.get_children())
        party_health = self.player_scan.get_party_health()

        for member_name, (current_health, max_health) in party_health.items():
            self.party_members_tree.insert('', 'end', values=(member_name, current_health, max_health))

    def update_spells_tab(self):
        """Update the spells tab with the latest known spells."""
        self.spells_tree.delete(*self.spells_tree.get_children())

        for spell in self.spell_collection.known_spells:
            self.spells_tree.insert('', 'end', values=(spell.id))

    def process_queue(self):
        try:
            while not self.spell_cast_queue.empty():
                spell_id, target_guid = self.spell_cast_queue.get()
                self.d3d_hook.queue_spell_cast(spell_id, target_guid)
            self.master.after(100, self.process_queue)
        except Exception as e:
            logging.error(f"Error in processing spell cast queue: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    
    # Initialize the memory reader
    memory_reader = WoWMemoryReader()
    player_scan = PlayerScan(memory_reader)
    
    # Initialize spell systems
    spell_collection = SpellCollection(memory_reader)
    d3d_hook = D3DHook(memory_reader, spell_collection)  # Create D3DHook instance
    
    # Initialize GUI with dependencies
    gui = OverlayGUI(root, player_scan, spell_collection, d3d_hook)
    
    # Hook D3D before main loop
    d3d_hook.hook_end_scene()
    
    try:
        root.mainloop()
    finally:
        # Ensure we unhook D3D when closing
        d3d_hook.unhook_end_scene()