from memory_reader import WoWMemoryReader
from offsets import Offsets
import keyboard

class GameObject:
    def __init__(self, pm, address):
        self.pm = pm
        self.address = address
        self.guid = self.read_guid()
        self.type = self.read_type()
        self.unit_fields_address = None
        self.x_pos = None
        self.y_pos = None
        self.z_pos = None
        self.rotation = None
        self.health = None
        self.max_health = None
        self.energy = None
        self.max_energy = None
        self.level = None
        self.load_positions()
        self.load_unit_data()

    def read_guid(self):
        try:
            return self.pm.read_uint64(self.address + Offsets.ObjectOffsets.Guid)
        except Exception as e:
            return None

    def read_type(self):
        try:
            return self.pm.read_int(self.address + Offsets.ObjectOffsets.Type)
        except Exception as e:
            return None

    def read_position(self, offset):
        """Reads a position value using the provided offset."""
        try:
            value = self.pm.read_float(self.address + offset)
            if self.is_valid_position_value(value):
                return value
            else:
                return 0.0
        except Exception as e:
            return 0.0

    def is_valid_position_value(self, value):
        """Validates whether the position value is within a reasonable range."""
        return -10000.0 < value < 10000.0

    def load_positions(self):
        """Attempts to load x, y, z positions and rotation."""
        self.x_pos = self.read_position(Offsets.ObjectOffsets.Pos_X)
        self.y_pos = self.read_position(Offsets.ObjectOffsets.Pos_Y)
        self.z_pos = self.read_position(Offsets.ObjectOffsets.Pos_Z)
        self.rotation = self.read_position(Offsets.ObjectOffsets.Rot)

    def load_unit_data(self):
        """Loads health, energy, max health, max energy, and level."""
        try:
            self.unit_fields_address = self.pm.read_uint(self.address + Offsets.ObjectOffsets.UnitFields)
            if self.unit_fields_address:
                self.health = self.pm.read_int(self.unit_fields_address + Offsets.UnitOffsets.Health)
                self.max_health = self.pm.read_int(self.unit_fields_address + Offsets.UnitOffsets.MaxHealth)
                self.energy = self.pm.read_int(self.unit_fields_address + Offsets.UnitOffsets.Mana)
                self.max_energy = self.pm.read_int(self.unit_fields_address + Offsets.UnitOffsets.MaxMana)
                self.level = self.pm.read_int(self.unit_fields_address + Offsets.UnitOffsets.Level)
        except Exception as e:
            pass

class ObjectManager:
    def __init__(self, memory_reader):
        self.pm = memory_reader
        self.objects = {}
        self.first_object = None
        self.local_guid = None
        self.load_addresses()

        # Set up keybind for activating the object manager
        keyboard.add_hotkey('0', self.enum_visible_objects)

    def load_addresses(self):
        """Load essential addresses for object manager."""
        try:
            client_connection = self.pm.read_uint(self.pm.base_address + Offsets.ObjectManager.StaticClientConnection - 0x400000)
            object_manager = self.pm.read_uint(client_connection + Offsets.ObjectManager.ObjectManagerOffset)
            self.first_object = self.pm.read_uint(object_manager + Offsets.ObjectManager.FirstObjectOffset)
            self.local_guid = self.pm.read_uint64(object_manager + Offsets.ObjectManager.LocalGuidOffset)
        except Exception as e:
            pass

    def enum_visible_objects(self):
        try:
            if not self.first_object:
                return

            current_object = self.first_object
            self.objects.clear()

            while current_object and current_object % 2 == 0:
                try:
                    obj = GameObject(self.pm, current_object)
                    if obj.guid is not None and obj.type in [Offsets.ObjectType.Player, Offsets.ObjectType.NPC]:  # Filtering object types
                        self.objects[obj.guid] = obj
                except Exception as e:
                    pass

                current_object = self.pm.read_uint(current_object + Offsets.ObjectManager.NextObjectOffset)
                if current_object is None:
                    break

        except Exception as e:
            pass

    def get_object_by_guid(self, guid):
        """Retrieves an object by its GUID."""
        return self.objects.get(guid, None)

    def get_objects_by_type(self, obj_type):
        """Retrieves all objects of a specific type (e.g., Player, NPC)."""
        return [obj for obj in self.objects.values() if obj.type == obj_type]

    def __str__(self):
        return f"ObjectManager(Objects: {len(self.objects)})"

    def get_local_player(self):
        """Returns the local player object."""
        return self.get_object_by_guid(self.local_guid)
