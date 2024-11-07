import logging
from offsets import Offsets
from memory_reader import WoWMemoryReader
import ctypes

class WowObject:
    def __init__(self):
        self.guid = 0
        self.name = "Unknown"
        self.current_health = 0
        self.max_health = 0
        self.x_pos = 0
        self.y_pos = 0
        self.z_pos = 0
        self.base_address = 0

    def clone(self):
        """Return a copy of the WowObject."""
        return WowObject().copy_from(self)

    def copy_from(self, other):
        """Copy data from another WowObject."""
        self.guid = other.guid
        self.name = other.name
        self.current_health = other.current_health
        self.max_health = other.max_health
        self.x_pos = other.x_pos
        self.y_pos = other.y_pos
        self.z_pos = other.z_pos
        self.base_address = other.base_address
        return self


class PlayerScan:
    def __init__(self, memory_reader: WoWMemoryReader):
        self.pm = memory_reader
        self.first_object = None
        self.local_guid = None
        self.local_player = WowObject()
        self.get_active_player = None
        self.get_active_player_obj = None
        self.current_players = []
        self.load_addresses()
    
    def load_addresses(self):
        client_connection = self.pm.read_uint(self.pm.base_address + Offsets.ObjectManager.StaticClientConnection - 0x400000)
        object_manager = self.pm.read_uint(client_connection + Offsets.ObjectManager.ObjectManagerOffset)
        self.first_object = self.pm.read_uint(object_manager + Offsets.ObjectManager.FirstObjectOffset)
        self.local_guid = self.pm.read_uint64(object_manager + Offsets.ObjectManager.LocalGuidOffset)
        self.get_active_player = self.pm.read_uint64(object_manager + Offsets.Globals.ClntObjMgrGetActivePlayer)
        self.get_active_player_obj = self.pm.read_uint64(object_manager + Offsets.Globals.ClntObjMgrGetActivePlayerObj)
        logging.info(f"Object Manager Base: {hex(object_manager)}, First Object: {hex(self.first_object)}")

    def get_local_player_name(self):
        player_name_address = self.pm.base_address + Offsets.Globals.PlayerName - 0x400000
        logging.info(f"Reading player name from address: {hex(player_name_address)}")
        player_name = self.pm.read_string(player_name_address)
        logging.info(f"Player Name Retrieved: {player_name}")
        return player_name

    def get_local_player_health_mana(self):
        current_object = self.first_object
        while current_object != 0 and current_object % 2 == 0:
            obj_guid = self.pm.read_uint64(current_object + Offsets.ObjectOffsets.Guid)
            if obj_guid == self.local_guid:
                unit_fields_address = self.pm.read_uint(current_object + Offsets.ObjectOffsets.UnitFields)
                health = self.pm.read_int(unit_fields_address + Offsets.UnitOffsets.Health)
                max_health = self.pm.read_int(unit_fields_address + Offsets.UnitOffsets.MaxHealth)
                mana = self.pm.read_int(unit_fields_address + Offsets.UnitOffsets.Mana)
                max_mana = self.pm.read_int(unit_fields_address + Offsets.UnitOffsets.MaxMana)
                return health, max_health, mana, max_mana
            current_object = self.pm.read_uint(current_object + Offsets.ObjectManager.NextObjectOffset)
        return None, None, None, None

    def ping(self):
        """Refreshes local player data and visible objects."""
        self.current_players.clear()
        self.local_player.base_address = self.get_object_base_by_guid(self.local_guid)
        if self.local_player.base_address != 0:
            self.update_object_info(self.local_player, self.local_guid)

        # Populate current_players with visible player objects
        current_object = self.first_object
        while current_object != 0 and current_object % 2 == 0:
            obj_type = self.pm.read_uint(current_object + Offsets.ObjectOffsets.Type)
            if obj_type == 4:  # Player type
                player = WowObject()
                player.guid = self.pm.read_uint64(current_object + Offsets.ObjectOffsets.Guid)
                player.name = self.get_player_name(player.guid)
                self.update_object_info(player, player.guid)
                self.current_players.append(player)
            current_object = self.pm.read_uint(current_object + Offsets.ObjectManager.NextObjectOffset)

    def get_player_list(self):
        """Return a list of visible player objects."""
        return [player.clone() for player in self.current_players]

    def update_object_info(self, obj, guid):
        """Retrieve and update position and health details for a given object."""
        obj.x_pos = self.pm.read_float(obj.base_address + Offsets.ObjectOffsets.Pos_X)
        obj.y_pos = self.pm.read_float(obj.base_address + Offsets.ObjectOffsets.Pos_Y)
        obj.z_pos = self.pm.read_float(obj.base_address + Offsets.ObjectOffsets.Pos_Z)
        unit_fields = self.pm.read_uint(obj.base_address + Offsets.ObjectOffsets.UnitFields)
        obj.current_health = self.pm.read_int(unit_fields + Offsets.UnitOffsets.Health)
        obj.max_health = self.pm.read_int(unit_fields + Offsets.UnitOffsets.MaxHealth)
        obj.name = self.get_player_name(guid)

    def get_player_name(self, guid):
        """Get player name by GUID."""
        try:
            mask = self.pm.read_uint(Offsets.Globals.NameStorePointer + Offsets.Globals.nameMask)
            base = self.pm.read_uint(Offsets.Globals.NameStorePointer + Offsets.Globals.nameBase)
            short_guid = guid & 0xffffffff
            offset = 12 * (mask & short_guid)
            current = self.pm.read_uint(base + offset + 8)

            while current != 0 and (current & 0x1) == 0:
                if self.pm.read_uint(current) == short_guid:
                    return self.pm.read_string(current + Offsets.Globals.nameString, 40)
                current = self.pm.read_uint(current + 4)
            return "Unknown"
        except Exception as e:
            logging.error(f"Error retrieving player name: {e}")
            return "Unknown"

    def get_object_base_by_guid(self, guid):
        """Finds the base address of an object by its GUID."""
        temp_object_base = self.first_object
        while temp_object_base != 0:
            current_guid = self.pm.read_uint64(temp_object_base + Offsets.ObjectOffsets.Guid)
            if current_guid == guid:
                return temp_object_base
            temp_object_base = self.pm.read_uint(temp_object_base + Offsets.ObjectManager.NextObjectOffset)
        return 0

    def get_party_health(self):
        party_member_health = {}

        # Iterate over attributes in Offsets.Party
        for member_name in dir(Offsets.Party):
            if not member_name.startswith("__"):  # Skip special attributes
                offset = getattr(Offsets.Party, member_name)
                guid = self.pm.read_uint64(self.pm.base_address + offset - 0x400000)

                # Start from the first object for each party member
                current_object = self.first_object
                while current_object != 0 and current_object % 2 == 0:
                    obj_guid = self.pm.read_uint64(current_object + Offsets.ObjectOffsets.Guid)
                    if guid == obj_guid:
                        unit_fields_address = self.pm.read_uint(current_object + Offsets.ObjectOffsets.UnitFields)
                        current_health = self.pm.read_int(unit_fields_address + Offsets.UnitOffsets.Health)
                        max_health = self.pm.read_int(unit_fields_address + Offsets.UnitOffsets.MaxHealth)
                        party_member_health[member_name] = (current_health, max_health)
                        break  # Exit the loop once the matching GUID is found for this member
                    current_object = self.pm.read_uint(current_object + Offsets.ObjectManager.NextObjectOffset)

        return party_member_health

    def get_local_player_guid(self):
        logging.info("Calling get_local_player_guid")
        try:
            local_guid_pointer = self.pm.base_address + Offsets.Globals.LocalGUID - 0x400000
            local_guid = self.pm.read_uint64(local_guid_pointer)
            logging.info(f"Local Player GUID Retrieved: {local_guid}")
            return local_guid
        except Exception as e:
            logging.error(f"Failed to retrieve Local Player GUID: {e}")
            return None
