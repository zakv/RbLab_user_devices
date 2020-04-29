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

import labscript_utils.h5_lock  # Must be imported be importing h5py
import h5py

import labscript_utils.h5_lock
from blacs.tab_base_classes import Worker
from labscript_devices.ZaberStageController.blacs_workers import \
    MockZaberInterface
from labscript_utils import dedent

# Create module globals for importing device-specific libraries then we'll
# import them later. That way labscript only needs those libraries installed if
# one of these devices is actually used.
pyvisa = None


class ElliptecError(Exception):
    def __init__(self, error_code):
        self.error_code = int(error_code)

        error_info = {
            1: "Communication time out.",
            2: "Mechanical time out.",
            3: "Command error or not supported.",
            4: "Value out of range.",
            5: "Module isolated.",
            6: "Module out of isolation.",
            7: "Initializing error.",
            8: "Thermal error.",
            9: "Busy.",
            10: ("Sensor Error (May appear during self test. If code persists "
                 "there is an error)."),
            11: ("Motor Error (May appear during self test. If code persists "
                 "there is an error)."),
            12: ("Out of Range (e.g. stage has been instructed to move beyond "
                 "its travel range)."),
            13: "Over Current error.",
        }

        if error_code == 0:
            message = "No error."
        elif error_code in error_info:
            message = f"Error {error_code}: {error_info[error_code]}"
        else:
            message = f"Error {error_code}: Undefined Error."

        super().__init__(message)


class _MockElliptecInterface(MockZaberInterface):
    def home(self, address):
        self.position = 0
        print(f"Mock device {address} homed.")


class _ElliptecInterface(object):
    # Properties that should be kept by subclasses.
    read_termination = '\r\n'
    default_timeout = 30e3  # milliseconds.

    def __init__(self, com_port):
        # Store com_port for future reference.
        self.com_port = com_port

        # Perform pyvisa import.
        global pyvisa
        import pyvisa

        # Connect to controller and configure communication settings.
        resource_manager = pyvisa.ResourceManager()
        self.visa_resource = resource_manager.open_resource(com_port)
        self.visa_resource.read_termination = self.read_termination
        self.visa_resource.timeout = self.default_timeout

    def close(self):
        self.visa_resource.close()

    def open(self):
        self.visa_resource.open()

    def _address_to_str(self, address):
        return '{:X}'.format(int(address))

    def write(self, address, message, **kwargs):
        # Construct message.
        addressed_message = self._address_to_str(address) + message

        # Print message to console for debugging purposes.
        print(addressed_message)

        self.visa_resource.write(addressed_message, **kwargs)

    def read(self, **kwargs):
        # Get response.
        response = self.visa_resource.read(**kwargs)

        # Print response to console for debugging purposes.
        print(response)
        # Print an empty line to visually separate next message.
        print()

        # Parse response.
        address = response[0]
        command = response[1:3]
        data = response[3:]

        return (address, command, data)

    def query(self, address, message, delay=None):
        self.write(address, message)

        if delay:
            time.sleep(delay)

        return self.read()

    def clear_receiving_state_machine(self):
        # Explained in Section 3 "Overview of the Communications Protocol" in
        # Elliptec Communication Manual.
        self.visa_resource.write('\r', termination=None)

    def get_info(self, address):
        # 'in' for info
        info_string = self.query(address, 'in')

        # TODO: Interpret info string.

        return info_string

    def check_status(self, address):
        # gs for get Status.
        _, _, status_code = self.query(address, 'gs')

        # Convert from string.
        status_code = int(status_code)

        # Raise exception if there was an error
        if status_code != 0:
            raise ElliptecError(status_code)

    def _position_counts_to_str(self, position_in_counts, n_bits=32):
        # Deal with the cast that position_in_counts is negative.
        if position_in_counts < 0:
            # Figure out value where numbers wrap around. For 2's complement
            # that value is 2^(n_bits -1).
            wrap_around_value = 2**(n_bits - 1)
            amount_exceeded = position_in_counts - (-wrap_around_value)
            position_in_counts = wrap_around_value + amount_exceeded

        # Convert to series of hex characters with captial letters and no
        # leading "0x".
        # '0' means pad with 0's, '>' means right-justify number, and 'X' for
        # hex.
        position_as_str = '{:0>8X}'.format(position_in_counts)

        return position_as_str

    def _position_str_to_counts(self, position_as_str, n_bits=None):
        # Set default value fo n_bits if necessary.
        if n_bits is None:
            # Each hex character gives 4 bits of information.
            n_bits = 4 * len(position_as_str)

        position_in_counts = int(position_as_str, 16)  # hex is base 16.

        # Figure out value where numbers wrap around. For 2's complement that
        # value is 2^(n_bits -1).
        wrap_around_value = 2**(n_bits - 1)

        # Deal with case that value exceeds wrap_around_value.
        if position_in_counts >= wrap_around_value:
            amount_exceeded = position_in_counts - wrap_around_value
            position_in_counts = -wrap_around_value + amount_exceeded

        return position_in_counts

    def home(self, address, clockwise=True):
        # 0 for clockwise, 1 for counterclockwise.
        direction = str(int(not clockwise))

        # 'ho' for home.
        return_message = self.query(address, 'ho' + direction)

        return return_message

    def get_position(self, address):
        # 'gp' for get position.
        _, _, position_as_str = self.query(address, 'gp')

        # Convert to python integer.
        position_in_counts = self._position_str_to_counts(position_as_str)

        return position_in_counts

    def move(self, address, position_in_counts):
        # Convert position to string in necessary format.
        position_as_str = self._position_counts_to_str(position_in_counts)

        # 'ma' for move absolute.
        return_message = self.query(address, 'ma' + position_as_str)

        return return_message

    def move_relative(self, address, position_in_counts):
        # Convert position to string in necessary format.
        position_as_str = self._position_counts_to_str(position_in_counts)

        # 'mr' for move relative.
        return_message = self.query(address, 'mr' + position_as_str)

        return return_message


class ElliptecWorker(Worker):
    def init(self):
        if self.mock:
            self.controller = _MockElliptecInterface(
                self.com_port,
            )
        else:
            self.controller = _ElliptecInterface(
                self.com_port,
            )

    def check_remote_values(self):
        remote_values = {}
        for connection in self.child_connections:
            remote_values[connection] = self.controller.get_position(
                connection)
        return remote_values

    def program_manual(self, values):
        for connection, value in values.items():
            self.controller.move(connection, value)
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
