#####################################################################
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript import StaticAnalogQuantity, IntermediateDevice, \
    set_passed_properties
import numpy as np


class ElliptecDevice(StaticAnalogQuantity):
    base_units = ''
    default_limits = (-np.inf, np.inf)
    description = "Generic Elliptec Device"

    @set_passed_properties(
        property_names={'connection_table_properties': ['limits']}
    )
    def __init__(self, *args, limits=None, **kwargs):
        """Static device for controlling the position of an Elliptec device.

        Args:
            *args (optional): These arguments will be passed to the `__init__()`
                method of the parent class (StaticAnalogQuantity).
            limits (tuple of two floats, optional): (Default=None) A tuple
                containing two floats. The first of which specifies the minimum
                value that the actuator should be allowed to go to, and the
                second of which specifies the maximum value.
            **kwargs (optional): Keyword arguments will be passed to the
                `__init__()` method of the parent class (StaticAnalogQuantity).
        """
        if limits is None:
            limits = self.default_limits
        StaticAnalogQuantity.__init__(self, *args, limits=limits, **kwargs)


# Classes for specific models, which have knowledge of their valid ranges:
class ELL14(ElliptecDevice):
    base_units = 'deg'
    default_limits = (0, 360)
    description = "ELL14 Rotation Mount"


class ElliptecInterfaceBoard(IntermediateDevice):
    allowed_children = [ElliptecDevice]

    @set_passed_properties(
        property_names={
            'connection_table_properties':
                ['com_port', 'mock'],
        }
    )
    def __init__(self, name, com_port, mock=False, **kwargs):
        """Device for controlling an Elliptec Interface Board.

        This class is intended to represent the interface board used to
        communicate with the Thorlabs Elliptec line of products. These boards
        accept a USB cable from a computer and a ribbon cable. The ribbon cable
        may then go directly to an Elliptec device, or to one or more ELLB bus
        distributors, which then in turn connect to one or more Elliptec
        devices.

        Add the Elliptec devices controlled by this interface board as child
        devices. You can use either a model-specific class or the generic
       `ElliptecDevice` class.

        Args:
            name (str): The name to give to this interface board.
            com_port (str): The serial connection of the interface board. This
                looks something like `'COM1'` on windows and `'/dev/USBtty0'` or
                similar on linux.
            mock (bool, optional): (Default=False) If set to True then no real
                interface board will be used. Instead a dummy that simply prints
                what a real device would do is used instead. This is helpful for
                testing and development.
            **kwargs: Further keyword arguents are passed to the `__init__()`
                method of the parent class (IntermediateDevice).
        """
        IntermediateDevice.__init__(self, name, None, **kwargs)
        self.BLACS_connection = com_port

    def generate_code(self, hdf5_file):
        IntermediateDevice.generate_code(self, hdf5_file)

        # Get dictionary of actuators with their connections as they keys.
        actuators = {
            actuator.connection: actuator for actuator in self.child_devices
        }

        # Make a sorted list of the connections.
        connections = sorted(actuators.keys())

        # Construct data for hdf5 file.
        dtypes = [(connection, np.float64) for connection in connections]
        static_value_table = np.empty(1, dtype=dtypes)
        for connection, actuator in actuators.items():
            static_value_table[connection][0] = actuator.static_value
        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('static_values', data=static_value_table)
