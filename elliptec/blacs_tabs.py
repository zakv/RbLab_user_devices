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


class ElliptecInterfaceBoardTab(DeviceTab):
    def initialise_GUI(self):
        # Capabilities
        self.base_units = 'counts'
        self.base_min = 0
        self.base_step = 100
        self.base_decimals = 0

        interface_board = self.settings['connection_table'].find_by_name(
            self.device_name,
        )
        self.com_port = interface_board.properties['com_port']
        self.mock = interface_board.properties['mock']

        # Create the AO output objects
        ao_prop = {}
        self.connection_serial_numbers = {}
        self.homing_settings = {}
        for elliptec_device in interface_board.child_list.values():
            # Get info about device.
            connection = elliptec_device.parent_port
            serial_number = elliptec_device.properties['serial_number']
            home_on_startup = elliptec_device.properties['home_on_startup']

            # Keep track of connection and serial number so they can be checked
            # in blacs_workers.py.
            self.connection_serial_numbers[connection] = serial_number

            # Keep track of which devices should be homed.
            self.homing_settings[connection] = home_on_startup

            # Info for AO output objects.
            base_min, base_max = elliptec_device.properties['limits']
            ao_prop[connection] = {
                'base_unit': self.base_units,
                'min': base_min,
                'max': base_max,
                'step': self.base_step,
                'decimals': self.base_decimals,
            }
        ao_prop = {
            c: ao_prop[c] for c in sorted(ao_prop.keys())
        }
        self.child_connections = list(ao_prop.keys())
        # Create the output objects
        self.create_analog_outputs(ao_prop)
        # Create widgets for output objects
        _, ao_widgets, _ = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("Actuators", ao_widgets))

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(False)

    def initialise_workers(self):
        # Create and set the primary worker
        self.create_worker(
            'main_worker',
            'userlib.user_devices.RbLab.elliptec.blacs_workers.ElliptecWorker',
            {
                'com_port': self.com_port,
                'mock': self.mock,
                'child_connections': self.child_connections,
                'connection_serial_numbers': self.connection_serial_numbers,
                'homing_settings': self.homing_settings,
            },
        )
        self.primary_worker = 'main_worker'
