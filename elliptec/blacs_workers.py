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
from collections import defaultdict
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
    """A class for raising errors issued by Elliptec Devices.

    Args:
        error_code (str of int): The error code returned by an Elliptec device.
    """

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
    """Class for simluating an Elliptec Device for testing and development.

    For testing purposes, all virtual devices have serial number '12345678'.

    Attributes:
        com_port (str): The name of the port used for the serial connection. On
            Windows this is typically something like `'COM1'`.
        position (str): The position of the simulated device. For simplicity (at
            the cost of realism) only one position stored and is shared between
            all virtual devices. That means moving one to `position=1` will
            effectively move all virtaul devices to `position=1`.
    """

    def home(self, address):
        self.position = 0
        print(f"Mock device {address} homed.")

    def get_serial_number(self, address):
        return '12345678'


class _ElliptecInterface(object):
    """Class for interfacing with Thorlabs Elliptec devices.

    This class contains the code necessary to send commands to Elliptec devices
    and read their responses. Communication occurs over a serial port and
    message structures are specified by the Elliptec API.

    A single instance of this interface class is responsible for communcation to
    all devices connected to a given interface board. For this reason, the
    bus address (not the COM port, but the 0 to F single-digit hex address) of
    the target device must be passed to many of the methods.

    Positions are always assumed to be in units of encoder counts here. The
    conversion to real units (for devices for which that makes sense) is handled
    separately by the unit conversion classes in `elliptec_unit_conversions.py`.

    The formatting for signed integers sent to/from the device is a bit
    complicated and is used in a few different methods, so it is documented once
    here. On the bus, all of the messages and data are sent as ASCII text, and
    conversion to python strings is taken care of behind the scenes by pyvisa.
    However, the conversion from text to actual numbers is taken care of by this
    class using its `self._position_counts_to_str` and
    `self._position_str_to_counts` methods. Signed integers are transmitted as a
    series of ASCII characters giving the number in hexadecimal in two's
    complement representation. The conversion from that string to a python
    integer is done in two steps. First the hex string is converted to an
    integer using `int(string, 16)`. That conversion effectively assumes that
    the string was a signed hex number, rather than a hex number in two's
    complement, so the value returned is always positive. The "wrapping around"
    in two's complement where large numbers actually represent negative numbers,
    is then implemented by hand.

    Note that since each hex character takes one byte but only represents 4 bits
    of information, sending a 32 bit signed integer actually requires sending 64
    bits of ASCII text.

    Attributes:
        com_port (str): The name of the port used for the serial connection. On
            Windows this is typically something like `'COM1'`.
        visa_resource (pyvisa.ResourceManager): All communication to/from the
            serial port is passed through `self.visa_resouce`, which is an
            instance of pyvisa's `ResourceManager` class.
        last_set_positions_in_counts (defaultdict): A defaultdict used to store
            the last position set for each actuator. This is used to support
            labscript's smart programming, where outputs are only updated when
            they are actually changed. The defaultdict is keyed by the single
            hex digit addresses of the devices, and the values are either `None`
            or the last position that the device was set to. Note that this may
            be different than the actual position of the device due to noise in
            the encoder.
    """
    # Properties that should be kept by subclasses.
    read_termination = '\r\n'
    default_timeout = 30e3  # milliseconds.

    def __init__(self, com_port):
        """Initialize the interface.

        Args:
            com_port (str): The name of the port used for the serial connection.
                On Windows this is typically something like `'COM1'`.
        """
        # Store com_port for future reference.
        self.com_port = com_port

        # Perform pyvisa import.
        global pyvisa
        import pyvisa

        # Connect to controller and configure communication settings.
        self.open_resource()

        # Keep track of last set position for smart programming.
        self.last_set_positions_in_counts = defaultdict(lambda: None)

    def open_resource(self):
        """Open a connection to the device.

        When blacs opens and tries to connect to many devices at once, the
        drivers sometimes fails to find the device. To work around that, this
        method tries a few times before giving up.

        Raises:
            pyvisa.errors.VisaIOError: Raised if the connection to the device
                fails multiple times. If this occurs, it's likely that the
                device is not connected.
        """
        need_to_connect = True
        n_connection_attempt = 1
        max_attempts = 10
        while need_to_connect and (n_connection_attempt <= max_attempts):
            try:
                # Print info for debugging.
                print(f"Connection attempt {n_connection_attempt}...")

                # Try to connect
                resource_manager = pyvisa.ResourceManager()
                self.visa_resource = resource_manager.open_resource(
                    self.com_port,
                )
                self.visa_resource.read_termination = self.read_termination
                self.visa_resource.timeout = self.default_timeout

                # If an error wasn't thrown, the connection was a success.
                need_to_connect = False
                print("Connected.")
            except pyvisa.errors.VisaIOError as err:
                n_connection_attempt += 1
                connection_error = err  # Save for re-raising later.
                time.sleep(1)

        # If we still haven't connected after multiple tries, give up and raise
        # the error.
        if need_to_connect:
            raise connection_error

    def open(self):
        """Re-open a connection to the device after calling `self.close()`."""
        self.visa_resource.open()

    def close(self):
        """Disconnect from the interface board.

        This frees the interface board, which is necessary before other programs
        can connect to it.
        """
        self.visa_resource.close()

    def _address_to_str(self, address):
        """Convert the address from an integer to a hex string.

        Args:
            address (int): The bus address of a device, which should be an
                integer between 0 and 15 inclusively.

        Returns:
            address (str): The bus address of the device, represented in
                hexadecimal as a string with a single character.
        """
        return '{:X}'.format(int(address))

    def write(self, address, message, **kwargs):
        """Send a message over the bus.

        This method combines the address and message content into a single
        string then sends the message over the bus. Messages are also printed to
        the console before being sent, which can be useful for debugging
        purposes.

        Args:
            address (int): The bus address of a device, which should be an
                integer between 0 and 15 inclusively.
            message (str): The instruction to send to the device. Do include the
                command and, if necessary, the data associated with the command.
                Do not include the address as this will be prepended
                automatically.
            **kwargs: Additional keyword arguments are passed to
                `self.visa_resource.write()`.
        """
        # Construct message.
        addressed_message = self._address_to_str(address) + message

        # Print message to console for debugging purposes.
        print(addressed_message)

        self.visa_resource.write(addressed_message, **kwargs)

    def read(self, **kwargs):
        """Read in a response from a device over the bus.

        Returns:
            address (str): The bus address of the device that sent the message.
                Note that here it is returned as a one-character string. The
                character gives the address of the device in hex.
            command (str): The command name corresponding to the command sent to
                the device. As mentioned in the Elliptec API documentation, the
                device responses always have two capital letters in the command
                part of the message. Typically these are the same two letters as
                the lower case letters used to issue the command. Sometimes the
                response's letters will be different though, such as when
                reporting an error in response to an invalid command.
            data (str): The data included in the response as an unparsed string.
            **kwargs: Additional keyword arguments are passed to
                `self.visa_resource.read()`.
        """
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
        """Send a command and receive the response.

        This is simply a convenience method that calls `self.write()` then
        `self.read()`.

        Args:
            address (int): The bus address of a device, which should be an
                integer between 0 and 15 inclusively.
            message (str): The instruction to send to the device. Do include the
                command and, if necessary, the data associated with the command.
                Do not include the address as this will be prepended
                automatically.
            delay (float, optional): (Default=None) The time to wait between
                issuing the command and reading the response. If set to None,
                there will be no extra delay.

        Returns:
            response (tuple): The tuple returned by `self.read()`. See that
                method's documentation for more information.
        """
        self.write(address, message)

        if delay:
            time.sleep(delay)

        return self.read()

    def clear_receiving_state_machine(self):
        """Clear the Elliptec device's receiving state machine.

        The effect of this command, which simply sends a carriage return
        character, is explained in Section 3 "Overview of the Communications
        Protocol" in the Elliptec API Manual.
        """
        self.visa_resource.write('\r', termination=None)

    def get_info(self, address):
        """Request device description from the Elliptec device.

        See the Elliptec API documentation for an explanation on how to
        interpret the response.

        Args:
            address (int): The bus address of a device, which should be an
                integer between 0 and 15 inclusively.

        Returns:
            response (tuple): The tuple returned by `self.read()`. See that
                method's documentation for more information.
        """
        # 'in' for info
        info_string = self.query(address, 'in')

        # TODO: Interpret info string.

        return info_string

    def get_serial_number(self, address):
        """Get the serial number of the Elliptec device.

        Args:
            address (int): The bus address of a device, which should be an
                integer between 0 and 15 inclusively.

        Returns:
            serial_number (str): The serial number of the device, as a string.
        """
        # Put parse info string back together so that indices here match up with
        # indices in Elliptec documentation.
        info_string = ''.join(self.get_info(address))
        serial_number = info_string[5:13]
        return serial_number

    def check_status(self, address):
        """Check the error status of the Elliptec device.

        This method does not return anything. It simply returns None if the
        device is ok, or raises an ElliptecError if the device is in an error
        state.

        Args:
            address (int): The bus address of a device, which should be an
                integer between 0 and 15 inclusively.

        Raises:
            ElliptecError: The error raised in the Elliptec device.
        """
        # gs for get Status.
        _, _, status_code = self.query(address, 'gs')

        # Convert from string.
        status_code = int(status_code)

        # Raise exception if there was an error
        if status_code != 0:
            raise ElliptecError(status_code)

    def _position_counts_to_str(self, position_in_counts, n_bits=32):
        """Convert a position in encoder counts to a string for a command.

        See this class's docstring for more information on the encoding and how
        it is done.

        Args:
            position_in_counts (int): The position in encoder counts as an
                integer.
            n_bits (int, optional): (Default=32) The number of bits that should
                be used to represent the number.

        Returns:
            position_as_str (str): The position represented as a string of hex
                characters in two's complement format for the given number of
                bits.
        """
        # Deal with the cast that position_in_counts is negative.
        if position_in_counts < 0:
            # Figure out value where numbers wrap around. For 2's complement
            # that value is 2^(n_bits -1).
            wrap_around_value = 2**(n_bits - 1)
            amount_exceeded = position_in_counts - (-wrap_around_value)
            position_in_counts = wrap_around_value + amount_exceeded

        # Round position to nearest integer.
        position_in_counts = round(position_in_counts)
        # Ensure numpy floats are converted to integers.
        position_in_counts = int(position_in_counts)

        # Convert to series of hex characters with captial letters and no
        # leading "0x".
        # '0' means pad with 0's, '>' means right-justify number, and 'X' for
        # hex.
        position_as_str = '{:0>8X}'.format(position_in_counts)

        return position_as_str

    def _position_str_to_counts(self, position_as_str, n_bits=None):
        """Convert a position in encoder counts as a hex string to an integer.

        See this class's docstring for more information on the encoding and how
        it is done.

        Args:
            position_as_str (str): The position represented as a string of hex
                characters in two's complement format for the given number of
                bits.
            n_bits (int, optional): (Default=None) The number of bits of the
                number. If set to None, it will be assumed that the number of
                bits is equal to the number of bits specified by the hex string,
                namely 4 bits per character.

        Returns:
            position_in_counts (int): The position in encoder counts as an
                integer.
        """
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
        """Home the Elliptec device.

        Note that calling this method clears the value stored for the given
        address in `self.last_set_positions_in_counts`.

        Args:
            address (int): The bus address of a device, which should be an
                integer between 0 and 15 inclusively.
            clockwise (bool, optional): (Default=True) If set to `True`, the
                device will home by moving clockwise. If set to `False`, the
                device will home by moving counterclockwise.

        Returns:
            response (tuple): The tuple returned by `self.read()`. See that
                method's documentation for more information.
        """
        # Clear the value of the last set position.
        self.last_set_positions_in_counts[address] = None

        # 0 for clockwise, 1 for counterclockwise.
        direction = str(int(not clockwise))

        # 'ho' for home.
        return_message = self.query(address, 'ho' + direction)

        return return_message

    def get_position(self, address):
        """Get the current position of the Elliptec device.

        Args:
            address (int): The bus address of a device, which should be an
                integer between 0 and 15 inclusively.

        Returns:
            position_in_counts (int): The position in encoder counts as an
                integer.
        """
        # 'gp' for get position.
        _, _, position_as_str = self.query(address, 'gp')

        # Convert to python integer.
        position_in_counts = self._position_str_to_counts(position_as_str)

        return position_in_counts

    def move(self, address, position_in_counts, fresh=True):
        """Move the Elliptec device to the desired position.

        Args:
            address (int): The bus address of a device, which should be an
                integer between 0 and 15 inclusively.
            position_in_counts (int): The desired position in encoder counts as
                an integer.
            fresh (bool, optional): (Default=`True`) If `fresh` is `False` and
                the new set position is the same as the previous one (as stored
                in self.last_set_positions_in_counts), then the device won't
                actually be instructed to move. If `fresh` is `True` then the
                device will be instructed to move even if it is set to the same
                position as last time. This is implemented to support
                labscript's smart programming.

        Returns:
            response (tuple): If the device was instructed to move, then the
                tuple returned by `self.read()` will be returned. See that
                method's documentation for more information. If the device was
                not instructed to move, then `response` will be set to `None`.
        """
        last_set_position_in_counts = self.last_set_positions_in_counts[address]
        if fresh or (position_in_counts != last_set_position_in_counts):
            # Convert position to string in necessary format.
            position_as_str = self._position_counts_to_str(position_in_counts)

            # 'ma' for move absolute.
            return_message = self.query(address, 'ma' + position_as_str)

            # Update last set position.
            self.last_set_positions_in_counts[address] = position_in_counts
        else:
            print(f"Used smart programming; didn't move.")
            return_message = None

        return return_message

    def move_relative(self, address, relative_position_in_counts):
        """Move the Elliptec device by the desired amount.

        Note that calling this method clears the value stored for the given
        address in `self.last_set_positions_in_counts`.

        Args:
            address (int): The bus address of a device, which should be an
                integer between 0 and 15 inclusively.
            relative_position_in_counts (int): The signed size of the desired
                shift in position, in encoder counts as an integer.

        Returns:
            response (tuple): The tuple returned by `self.read()`. See that
                method's documentation for more information.
        """
        # Clear the value of the last set position.
        self.last_set_positions_in_counts[address] = None

        # Convert position to string in necessary format.
        position_as_str = self._position_counts_to_str(
            relative_position_in_counts
        )

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

        # Check that serial numbers of devices match values in connection
        # table.
        self.check_serial_numbers()

        # Home actuators that are configured to be homed on startup.
        self.do_homing()

    def check_serial_numbers(self):
        """Compare serial numbers in connection table to actual serial numbers.

        This method iterates over the Elliptec devices connected to this
        interface bus in the connection table and ensures that their actual
        serial numbers match their values in the connection table. If any do not
        match, a `ValueError` is raised.

        Raises:
            ValueError: If any devices have a serial number that doesn't match
                the value specified in the connection table, a `ValueError` is
                raised.
        """
        # Compare actual serial number to serial number in connection table for
        # each device.
        for connection, serial_number in self.connection_serial_numbers.items():
            # Get the actual serial number of the device at this connection.
            actual_serial_number = self.controller.get_serial_number(
                connection,
            )

            # Make sure serial_number is a string since actual_serial_number
            # is.
            serial_number = str(serial_number)

            # Ensure that the two are the same.
            if serial_number != actual_serial_number:
                message = (f"Device with connection {connection} has serial "
                           f"number '{actual_serial_number}' but is specified "
                           f"to have serial number '{serial_number}' in the "
                           "connection table.")
                raise ValueError(message)

    def do_homing(self):
        """Home devices that are configured to be homed on startup."""
        for connection, home_on_startup in self.homing_settings.items():
            if home_on_startup:
                self.controller.home(connection)

    def check_remote_values(self):
        remote_values = {}
        for connection in self.child_connections:
            remote_values[connection] = self.controller.get_position(
                connection)
        return remote_values

    def move(self, values, fresh=True):
        for connection, value in values.items():
            self.controller.move(connection, value, fresh=fresh)
        return self.check_remote_values()

    def program_manual(self, values):
        return self.move(values, fresh=True)

    def transition_to_buffered(
            self, device_name, h5file, initial_values, fresh):
        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['/devices/' + device_name]
            if 'static_values' in group:
                data = group['static_values']
                values = {name: data[0][name] for name in data.dtype.names}
            else:
                values = {}
        return self.move(values, fresh=fresh)

    def transition_to_manual(self):
        return True

    def abort_buffered(self):
        return True

    def abort_transition_to_buffered(self):
        return True

    def shutdown(self):
        self.controller.close()
