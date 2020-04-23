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
        from collections import defaultdict
        self.position = 0

    def home(self):
        self.is_homed = True
        print("Mock device homed.")

    def move(self, position):
        print(f"Mock move device to position {position}")
        self.position = position

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

        # Add path to kinesis .NET libraries if provided.
        if kinesis_path and kinesis_path not in sys.path:
            sys.path.append(kinesis_path)

        # Use pythonnet to import necessary kinesis .NET libraries.
        try:
            # Import DeviceManagerCLI into .NET's Common Language Runtime (CLR)
            # so we can then import it into python.
            global DeviceManagerCLI
            clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
            from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI  # pylint: disable=import-error
            # Import class that controls KDC101.
            global KCubeDCServo
            clr.AddReference("Thorlabs.MotionControl.KCube.DCServoCLI")
            from Thorlabs.MotionControl.KCube.DCServoCLI import KCubeDCServo  # pylint: disable=import-error
        except System.IO.FileNotFoundException:
            msg = """Could not find Thorlabs Kinesis drivers, ensure that the
                Kinesis folder is included in sys.path."""
            raise System.IO.FileNotFoundException(msg)

        # Build device list so that drivers can find the controllers when we
        # try to connect to them.
        DeviceManagerCLI.BuildDeviceList()

        # Create the KCube DCServo device.
        self.controller = KCubeDCServo.CreateDevice(str(self.serial_number))

        # Open a connection to the device.
        self.controller.Connect(str(self.serial_number))

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

        # The API requires stage type to be specified.
        # Name of motor or stage being controlled (check in Kinesis GUI).
        # device_settings_name = 'Z812'
        # motor_configuration.DeviceSettingsName = device_settings_name

        # Get the device unit converter.
        motor_configuration.UpdateCurrentConfiguration()

    @property
    def is_homed(self):
        return self.controller.Status.IsHomed

    def home(self):
        print("Homing...")
        self.controller.Home(self.default_timeout)
        print("Finshed Homing.")

    def move(self, position):
        # System.Decimal doesn't handle numpy floats, so make sure it's a normal
        # built-in python float.
        position = float(position)
        self.controller.MoveTo(System.Decimal(position), self.default_timeout)

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

    def program_manual(self, values):
        for _, value in values.items():
            self.controller.move(value)
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
