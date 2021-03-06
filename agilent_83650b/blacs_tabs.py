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
from ._hardware_capabilities import agilent_83650b


class Agilent83650BTab(DeviceTab):
    def initialise_GUI(self):
        # Create DDS Output objects
        dds_prop = {'dds 0': {}}
        dds_prop['dds 0']['freq'] = agilent_83650b['freq']
        dds_prop['dds 0']['amp'] = agilent_83650b['amp']
        dds_prop['dds 0']['gate'] = {}
        self.create_dds_outputs(dds_prop)

        # Create widgets for output objects and auto place the widgets in the
        # UI.
        dds_widgets, ao_widgets, do_widgets = self.auto_create_widgets()
        self.auto_place_widgets(("DDS Outputs", dds_widgets))

        # Get properties from connection table.
        device = self.settings['connection_table'].find_by_name(
            self.device_name,
        )
        self.com_port = device.properties['com_port']
        self.gpib_address = device.properties['gpib_address']
        self.mock = device.properties['mock']
        # Get the child connection's setting for ramp_between_frequencies. There
        # is only ever one child output.
        children = list(device.child_list.values())
        output = children[0]
        self.ramp_between_frequencies = output.properties['ramp_between_frequencies']
        self.ramp_step_size = output.properties['ramp_step_size']
        self.ramp_min_step_duration = output.properties['ramp_min_step_duration']

        # Create list of parent ports for child connections.
        self.child_connections = [child.parent_port for child in children]

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(True)

    def initialise_workers(self):
        # Create and set the primary worker
        self.create_worker(
            'main_worker',
            'user_devices.RbLab.agilent_83650b.blacs_workers.Agilent83650BWorker',
            {
                'com_port': self.com_port,
                'gpib_address': self.gpib_address,
                'mock': self.mock,
                'ramp_between_frequencies': self.ramp_between_frequencies,
                'ramp_step_size': self.ramp_step_size,
                'ramp_min_step_duration': self.ramp_min_step_duration,
                'child_connections': self.child_connections,
            },
        )
        self.primary_worker = 'main_worker'
