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
from labscript import StaticAnalogQuantity, IntermediateDevice, set_passed_properties
import numpy as np


class BrushedDCServoMotor(StaticAnalogQuantity):

    default_limits = (0, np.inf)
    description = "Generic Actuator"

    @set_passed_properties(
        property_names={"connection_table_properties": ["limits"]}
    )
    def __init__(self, *args, limits=None, **kwargs):
        """Static device for controlling the position of a mechanical actuator.

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
class Z812(BrushedDCServoMotor):
    default_limits = (0, 12)
    description = "Z812 Brushed DC Servo Motor"


class KDC101(IntermediateDevice):
    allowed_children = [BrushedDCServoMotor]

    @set_passed_properties(
        property_names={
            "connection_table_properties":
                ["serial_number", "allow_homing", "mock"],
        }
    )
    def __init__(self, name, serial_number,
                 allow_homing, mock=False, **kwargs):
        """Device for controlling a KDC101.

        Add the brushled DC servo motor controlled by this KDC101 as a child
        device. You can use either a model-specific class or the generic
       `BrushedDCServoMotor` class.

        Args:
            name (str): The name to give to this group of actuators.
            serial_number (int): The serial number of the KDC101, which is
                labeled on the device itself. Alternatively it can be determined
                by looking at the device in the Kinesis GUI software.
            allow_homing (bool): If the device needs to be homed (i.e. it has
                not been homed since it was last powered on) then it will be
                homed if allow_homing is True. If allow_homing is False and the
                device is not already homed, a RuntimeError will be raised. This
                is useful e.g. if the actuator controls a high power beam which
                must be turned off manually before homing to ensure that the
                beam isn't sent in an unsafe direction during the homing
                procedure. Homing can be done using the Kinesis GUI in that
                case, once the user has ensured that it is safe to do so.
            mock (bool, optional): (Default=False) If set to True then no real
                actuator will be used. Instead a dummy that simply prints what
                a real stage would do is used instead. This is helpful for
                testing and development.
            **kwargs: Further keyword arguents are passed to the `__init__()`
                method of the parent class (IntermediateDevice).
        """
        IntermediateDevice.__init__(self, name, None, **kwargs)
        self.BLACS_connection = serial_number

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
