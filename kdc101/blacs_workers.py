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
clr = None
System = None
DeviceManagerCLI = None
KCubeDCServo = None


class _MockKDC101Interface(MockZaberInterface):
    def __init__(self, serial_number, kinesis_path):
        self.serial_number = serial_number
        self.is_homed = False
        self.kinesis_path = kinesis_path
        self.position = 0
        # Keep track of last set position for smart programming.
        self.last_set_position = None

    def home(self):
        self.is_homed = True
        print("Mock device homed.")

    def move(self, position, fresh=True):
        if fresh or (position != self.last_set_position):
            self.position = position
            self.last_set_position = position
            print(f"Mock moved device to position {position}.")
        else:
            print(f"Mock used smart programming; didn't move.")

    def get_position(self):
        return self.position


class _KDC101Interface(object):

    # Configuraion constants.
    default_timeout = int(60e3)  # Timeout in ms.
    polling_interval = 250  # Polling period in ms.

    def __init__(self, serial_number, kinesis_path):
        # Store initialization parameters.
        self.serial_number = serial_number
        self.kinesis_path = kinesis_path

        # Import the required python libraries.
        self._import_python_libraries()

        # Import the kinesis .NET libraries.
        self._import_kinesis_libraries()

        # Open a connection to the controller.
        self.open()

        # Start the device polling.
        # The polling loop requests regular status requests to the motor to
        # ensure the program keeps track of the device.
        self.controller.StartPolling(int(self.polling_interval))
        time.sleep(0.5)

        # Enable the channel otherwise any move is ignored.
        self.controller.EnableDevice()
        time.sleep(0.5)

        # Call LoadMotorConfiguration on the device to initialize the
        # DeviceUnitConverter object required for real world unit parameters.
        # Loads configuration information into channel.
        motor_configuration = self.controller.LoadMotorConfiguration(
            str(self.serial_number)
        )

        # The .NET help files suggest the following step, but it seems to be
        # fine to skip it. That may required connecting to the device with the
        # Kinesis GUI first though.
        # The API requires stage type to be specified.
        # Name of motor or stage being controlled (check in Kinesis GUI).
        # device_settings_name = 'Z812'
        # motor_configuration.DeviceSettingsName = device_settings_name

        # Get the device unit converter.
        motor_configuration.UpdateCurrentConfiguration()

        # Keep track of last set position for smart programming.
        self.last_set_position = None

    def _import_python_libraries(self):
        # Import required python libraries.
        global clr
        global System
        try:
            import clr
            import System
        except ImportError:
            message = """Could not import clr and System. Please ensure that
                pythonnet is installed, which is possible via pip or conda."""
            raise ImportError(dedent(message))

    def _import_kinesis_libraries(self):
        # Add path to kinesis .NET libraries if provided.
        if self.kinesis_path and (self.kinesis_path not in sys.path):
            sys.path.append(self.kinesis_path)

        # Use pythonnet to import necessary kinesis .NET libraries.
        try:
            # Import DeviceManagerCLI into .NET's Common Language Runtime (CLR)
            # so we can then import it into python.
            global DeviceManagerCLI
            clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
            from Thorlabs.MotionControl import DeviceManagerCLI  # pylint: disable=import-error

            # Import class that controls KDC101.
            global KCubeDCServo
            clr.AddReference("Thorlabs.MotionControl.KCube.DCServoCLI")
            from Thorlabs.MotionControl.KCube.DCServoCLI import KCubeDCServo  # pylint: disable=import-error
        except System.IO.FileNotFoundException:
            msg = """Could not find Thorlabs Kinesis drivers, ensure that the
                Kinesis folder is included in sys.path."""
            raise System.IO.FileNotFoundException(msg)

    def open(self):
        """Open a connection to the device.

        When blacs opens and tries to connect to many devices at once, the
        drivers sometimes fails to find the device. To work around that, this
        method tries a few times before giving up.

        Raises:
            DeviceNotReadyException: Raised if the connection to the device
                fails multiple times. If this occurs, it's likely that the
                device is not connected, or that the serial number provided is
                incorrect.
        """
        need_to_connect = True
        n_connection_attempt = 1
        max_attempts = 10
        while need_to_connect and (n_connection_attempt <= max_attempts):
            try:
                # Print info for debugging.
                print(f"Connection attempt {n_connection_attempt}...")

                # Build device list so that drivers can find the controller.
                DeviceManagerCLI.DeviceManagerCLI.BuildDeviceList()

                # Create the KCube DCServo device.
                self.controller = KCubeDCServo.CreateDevice(
                    str(self.serial_number)
                )

                # Try to open the connection.
                self.controller.Connect(str(self.serial_number))

                # If an error wasn't thrown, the connection was a success.
                need_to_connect = False
                print("Connected.")
            except DeviceManagerCLI.DeviceNotReadyException as err:
                n_connection_attempt += 1
                connection_error = err  # Save for re-raising later.
                time.sleep(1)

        # If we still haven't connected after multiple tries, give up and raise
        # the error.
        if need_to_connect:
            raise connection_error

    @property
    def is_homed(self):
        return self.controller.Status.IsHomed

    def home(self):
        print("Homing...")
        self.controller.Home(self.default_timeout)
        print("Finshed Homing.")

    def move(self, position, fresh=True):
        # System.Decimal doesn't handle numpy floats, so make sure it's a normal
        # built-in python float.
        position = float(position)
        if fresh or (position != self.last_set_position):
            self.controller.MoveTo(
                System.Decimal(position),
                self.default_timeout,
            )
            self.last_set_position = position
            print(f"Moved device to position {position}.")
        else:
            print(f"Used smart programming; didn't move.")

    def get_position(self):
        return float(str(self.controller.Position))

    def close(self):
        # Stop the driver's periodic checks on the actuator position.
        self.controller.StopPolling()

        # Close the connection to the controller.
        self.controller.Disconnect(True)


class KDC101Worker(Worker):
    def init(self):
        if self.mock:
            self.controller = _MockKDC101Interface(
                self.serial_number,
                self.kinesis_path,
            )
        else:
            self.controller = _KDC101Interface(
                self.serial_number,
                self.kinesis_path,
            )

        if not self.controller.is_homed:
            if self.allow_homing:
                self.controller.home()
            else:
                self.controller.close()
                message = """Device isn't homed and is not allowed to home.
                    Please home using Kinesis GUI then restart device."""
                raise RuntimeError(dedent(message))

    def check_remote_values(self):
        remote_values = {}
        for connection in self.child_connections:
            remote_values[connection] = self.controller.get_position()
        return remote_values

    def _move(self, values, fresh=True):
        for _, position in values.items():
            self.controller.move(position, fresh=fresh)
        return self.check_remote_values()

    def program_manual(self, values):
        return self._move(values, fresh=True)

    def transition_to_buffered(
            self, device_name, h5file, initial_values, fresh):
        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['/devices/' + device_name]
            if 'static_values' in group:
                data = group['static_values']
                values = {name: data[0][name] for name in data.dtype.names}
            else:
                values = {}
        return self._move(values, fresh=fresh)

    def transition_to_manual(self):
        return True

    def abort_buffered(self):
        return True

    def abort_transition_to_buffered(self):
        return True

    def shutdown(self):
        self.controller.close()
