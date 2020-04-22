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


class Actuator(StaticAnalogQuantity):

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


# Child classes for specific models of stages, which have knowledge of their valid
# ranges:
class KDC101(Actuator):
    default_limits = (0, 76346)
    description = "KDC101 Servo Motor Controller"


class ActuatorsController(IntermediateDevice):
    allowed_children = [Actuator]

    @set_passed_properties(
        property_names={"connection_table_properties": ["mock"]}
    )
    def __init__(self, name, mock=False, **kwargs):
        """Device for controlling a number of actuators.

        Add stages as child devices, either by using one of the model-specific
        classes in this module, or the generic `Actuator` class.

        Args:
            name (str): The name to give to this group of actuators.
            mock (bool, optional): (Default=False) If set to True then no real
                actuator will be used. Instead a dummy that simply prints what
                a real stage would do is used instead. This is helpful for
                testing and development.
            **kwargs: Further keyword arguents are passed to the `__init__()`
                method of the parent class (IntermediateDevice).
        """
        IntermediateDevice.__init__(self, name, None, **kwargs)

    def generate_code(self, hdf5_file):
        IntermediateDevice.generate_code(self, hdf5_file)
        stages = {stage.connection: stage for stage in self.child_devices}
        connections = sorted(stages, key=get_device_number)
        dtypes = [(connection, int) for connection in connections]
        static_value_table = np.empty(1, dtype=dtypes)
        for connection, stage in stages.items():
            static_value_table[connection][0] = stage.static_value
        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('static_values', data=static_value_table)
