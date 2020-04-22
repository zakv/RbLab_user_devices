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
import sys
import time

import h5py

import labscript_utils.h5_lock
from blacs.tab_base_classes import Worker
from labscript_devices.ZaberStageController.blacs_workers import \
    MockZaberInterface
from labscript_utils import dedent

clr = None
System = None

TIMEOUT = 60


class MockActuatorsGroup(MockZaberInterface):
    def __init__(self):
        from collections import defaultdict
        self.positions = defaultdict(int)


class ActuatorsGroup(object):
    def __init__(self):
        global clr
        global System
        try:
            import clr
            from System import Decimal
        except ImportError:
            message = """Could not import clr and System. Please ensure that
                pythonnet is installed, which is possible via pip or conda."""
            raise ImportError(dedent(message))

    def move(self, serial_number, position):
        device = zaber.BinaryDevice(self.port, device_number)
        device.move_abs(position)
        deadline = monotonic() + TIMEOUT
        while device.get_position() != position:
            if monotonic() > deadline:
                msg = "Device did not move to requested position within timeout"
                raise TimeoutError(msg)

    def get_position(self, device_number):
        device = zaber.BinaryDevice(self.port, device_number)
        return device.get_position()

    def close(self):
        self.port.close()


class ActuatorsWorker(Worker):
    def init(self):
        if self.mock:
            self.controller = MockActuatorsGroup()
        else:
            self.controller = ActuatorsGroup()

    def check_remote_values(self):
        remote_values = {}
        for connection in self.child_connections:
            device_number = get_device_number(connection)
            remote_values[connection] = self.controller.get_position(
                device_number)
        return remote_values

    def program_manual(self, values):
        for connection, value in values.items():
            device_number = get_device_number(connection)
            self.controller.move(device_number, int(round(value)))
        return self.check_remote_values()

    def transition_to_buffered(
            self, device_name, h5file, initial_values, fresh):
        with h5py.File(h5file) as hdf5_file:
            group = hdf5_file['/devices/' + device_name]
            if 'static_values' in group:
                data = group['static_values']
                values = {name: data[0][name] for name in data.dtype.names}
            else:
                values = {}
        return self.program_manual(values)

    def transition_to_manual(self):
        return True

    def abort_buffered(self):
        return True

    def abort_transition_to_buffered(self):
        return True

    def shutdown(self):
        self.controller.close()
