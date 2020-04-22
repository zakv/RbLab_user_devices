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
from blacs.device_base_class import DeviceTab


class ActuatorsGroupTab(DeviceTab):
    def initialise_GUI(self):
        # Capabilities
        self.base_units = 'steps'
        self.base_min = 0
        self.base_step = 100
        self.base_decimals = 0

        device = self.settings['connection_table'].find_by_name(
            self.device_name,
        )
        self.mock = device.properties['mock']

        # Create the AO output objects
        ao_prop = {}
        for actuator in device.child_list.values():
            connection = actuator.parent_port
            base_min, base_max = actuator.properties['limits']
            ao_prop[connection] = {
                'base_unit': self.base_units,
                'min': base_min,
                'max': base_max,
                'step': self.base_step,
                'decimals': self.base_decimals,
            }
        # TODO: Sort actuators
        # ao_prop = {
        #     c: ao_prop[c] for c in sorted(ao_prop, key=get_device_number)
        # }
        self.child_connections = list(ao_prop.keys())
        # Create the output objects
        self.create_analog_outputs(ao_prop)
        # Create widgets for output objects
        _, ao_widgets, _ = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("Actuators", ao_widgets))

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(False)  # TODO: Implement?

    def initialise_workers(self):
        # Create and set the primary worker
        self.create_worker(
            'main_worker',
            'userlib.user_devices.RbLab.actuators_group.blacs_workers.ActuatorsGroupWorker',
            {
                'mock': self.mock,
                'child_connections': self.child_connections,
            },
        )
        self.primary_worker = 'main_worker'
