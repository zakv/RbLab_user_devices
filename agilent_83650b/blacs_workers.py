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
import time

import labscript_utils.h5_lock  # Must be imported before importing h5py.
import h5py

from blacs.tab_base_classes import Worker
from labscript_utils import dedent

# Create module globals for importing device-specific libraries then we'll
# import them later. That way labscript only needs those libraries installed if
# one of these devices is actually used.
pyvisa = None


class _Agilent83650B():
    def __init__(self, com_port, gpib_address, ramp_between_frequencies):
        # Store argument values.
        self.com_port = com_port
        self.gpib_address = gpib_address
        self.ramp_between_frequencies = ramp_between_frequencies

        # Get connection to the device going.
        self._import_python_libraries()
        self._open_resource()
        self._configure_gpib_interface

        # Keep track of last set output settings for smart programming.
        self.last_set_values = defaultdict(lambda: None)

        # Keep track of actual values output settings so they can be returned
        # when using smart programming.
        self.last_actual_values = defaultdict(lambda: None)

    def _import_python_libraries(self):
        # Import required python libraries.
        global pyvisa
        try:
            import pyvisa
        except ImportError:
            message = """Could not import pyvisa. Please ensure that pyvisa is
                installed, which is possible via pip or conda."""
            raise ImportError(dedent(message))

    def _open_resource(self):
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
        while need_to_connect:
            try:
                # Print info for debugging.
                print(f"Connection attempt {n_connection_attempt}...")

                # Try to connect
                resource_manager = pyvisa.ResourceManager()
                self.visa_resource = resource_manager.open_resource(
                    self.com_port,
                )

                # If an error wasn't thrown, the connection was a success.
                need_to_connect = False
                print("Connected.")
            except pyvisa.errors.VisaIOError as err:
                # Give up if we've hit the max number of attemps, or wait 1
                # second then try again.
                if n_connection_attempt >= max_attempts:
                    raise err
                else:
                    time.sleep(1)
                    n_connection_attempt += 1

    def _configure_gpib_interface(self):
        """Configure a Prologix GPIB-USB converter for communcation.

        This method is not very general. It assumes that the 83650B is connected
        via a Prologix USB-GPIB converter. If a different GPIB interface is
        used, it may be necessary to create a new labscript device which
        inherits the classes from here but overrides this method. It may be
        necessary to override the `self.write()`, `self.query()`, and/or
        `self.read()` methods of this class as well.
        """
        # Commands beginning with '++' set options of the Prologix USB-GPIB
        # converter and aren't sent as messages on the GPIB bus.

        # Put the converter in "controller" mode to control the 83650B.
        self.write('++mode 1')
        # Turn off auto-read which errors for commands with no response.
        self.write('++auto 0')
        # Specify GPIB bus address of this device.
        self.write(f'++addr {self.gpib_address}')

        # GPIB messages need to be terminated with ascii character number ten
        # and EOI (see synth manual pdf page 109 and Prologix manual page 10).
        # This is probably not necessary but does work.
        # Terminate GPIB messages with ascii character 10.
        self.write('++eos 2')
        # Enable EOI at end of GPIB messages.
        self.write('++eoi 1')

    def open(self):
        """Re-open a connection to the device after calling `self.close()`."""
        self.visa_resource.open()

    def close(self):
        """Close the connection to the device."""
        self.visa_resource.close()

    def write(self, *args, **kwargs):
        print(f"Sending: '{args[0]}'")
        return self.visa_resource.write(*args, **kwargs)

    def query(self, *args, **kwargs):
        return self.visa_resource.query(*args, **kwargs)

    def read(self):
        response = self.query('++read')
        # Remove trailing newline
        response = response.strip()
        print(f"Received: '{response}'\n")
        return response

    @property
    def output_enabled(self):
        """Whether or not the synth's output is enabled."""
        # Read the power state.
        self.write(':POWer:STATe?')
        output_enabled = self.read()

        # Convert '1\n' or '0\n' to boolean.
        output_enabled = bool(int(output_enabled))
        return output_enabled

    @output_enabled.setter
    def output_enabled(self, output_enabled):
        # Convert the boolean input into 0 or 1.
        output_enabled_int = int(bool(output_enabled))
        # Set output to desired state.
        self.write(f':POWer:STATe {output_enabled_int}')
        self.last_set_values['output_enabled'] = output_enabled
        self.last_actual_values['output_enabled'] = self.output_enabled

    def smart_set_output_enabled(self, output_enabled, fresh=False):
        if fresh or (output_enabled != self.last_set_values['output_enabled']):
            self.output_enabled = output_enabled
            print(f"Set ouptut_enabled to {output_enabled}.")
        else:
            print(f"Used smart programming; didn't change output_enabled.")
        return self.last_actual_values['output_enabled']

    @property
    def frequency(self):
        """The CW frequency of the synth in Hz."""
        self.write(':FREQuency:CW?')
        frequency = float(self.read())
        return frequency

    @frequency.setter
    def frequency(self, frequency):
        if self.ramp_between_frequencies:
            # TODO: implement ramping between frequencies.
            raise NotImplementedError(
                "Ramping between frequencies is not yet implemented."
            )
        else:
            self.write(f':FREQuency:CW {frequency} Hz')
        self.last_set_values['frequency'] = frequency
        self.last_actual_values['frequency'] = self.frequency

    def smart_set_frequency(self, frequency, fresh=False):
        if fresh or (frequency != self.last_set_values['frequency']):
            self.frequency = frequency
            print(f"Set frequency to {frequency}.")
        else:
            print("Used smart programming; didn't change frequency.")
        return self.last_actual_values['frequency']

    @property
    def power(self):
        """The output power of the synth in dBm."""
        self.write(':POWer:LEVel?')
        power = float(self.read())
        return power

    @power.setter
    def power(self, power):
        self.write(f':POWer:LEVel {power:.2f} dBm')
        self.last_set_values['power'] = power
        self.last_actual_values['power'] = self.power

    def smart_set_power(self, power, fresh=False):
        if fresh or (power != self.last_set_values['power']):
            self.power = power
            print(f"Set power to {power}.")
        else:
            print("Used smart programming; didn't change power.")
        return self.last_actual_values['power']


class _MockAgilent83650B(_Agilent83650B):
    def __init__(self, com_port, gpib_address, ramp_between_frequencies):
        # Store argument values.
        self.com_port = com_port
        self.gpib_address = gpib_address
        self.ramp_between_frequencies = ramp_between_frequencies

        # Keep track of last set output settings for smart programming.
        self.last_set_values = defaultdict(lambda: None)

        # Store mocked parameters. We'll use somewhat random values for initial
        # settings.
        self._mock_output_enabled = True
        self._mock_frequency = 100e6
        self._mock_power = 0.0

    def open(self):
        pass

    def close(self):
        pass

    @property
    def output_enabled(self):
        """Whether or not the synth's output is enabled."""
        return self._mock_output_enabled

    @output_enabled.setter
    def output_enabled(self, output_enabled):
        self._mock_output_enabled = output_enabled
        self.last_set_values['output_enabled'] = output_enabled

    @property
    def frequency(self):
        """The CW frequency of the synth in Hz."""
        return self._mock_frequency

    @frequency.setter
    def frequency(self, frequency):
        self._mock_frequency = frequency
        self.last_set_values['frequency'] = frequency

    @property
    def power(self):
        """The output power of the synth in dBm."""
        return self._mock_power

    @power.setter
    def power(self, power):
        self._mock_power = power
        self.last_set_values['power'] = power


class Agilent83650BWorker(Worker):
    def init(self):
        if self.mock:
            self.synth = _MockAgilent83650B(
                self.com_port,
                self.gpib_address,
                self.ramp_between_frequencies,
            )
        else:
            self.synth = _Agilent83650B(
                self.com_port,
                self.gpib_address,
                self.ramp_between_frequencies,
            )

    def check_remote_values(self):
        remote_values = {}
        # There should only be one connection ('dds 0') but we'll iterate anyway
        # to extract the value from the dictionary.
        for connection in self.child_connections:
            remote_values[connection] = {}
            remote_values[connection]['freq'] = self.synth.frequency
            remote_values[connection]['amp'] = self.synth.power
            remote_values[connection]['gate'] = self.synth.output_enabled
        return remote_values

    def set_output_settings(self, values, fresh=False):
        actual_values = {}
        for connection, values_dict in values.items():
            actual_values[connection] = {}
            # Set frequency.
            frequency = values_dict['freq']
            actual_frequency = self.synth.smart_set_frequency(
                frequency,
                fresh=fresh,
            )
            actual_values[connection]['freq'] = actual_frequency
            # Set power.
            power = values_dict['amp']
            actual_power = self.synth.smart_set_power(
                power,
                fresh=fresh,
            )
            actual_values[connection]['power'] = actual_power
            # Set output enabled.
            output_enabled = values_dict['gate']
            actual_output_enabled = self.synth.smart_set_output_enabled(
                output_enabled,
                fresh=fresh,
            )
            actual_values[connection]['gate'] = actual_output_enabled
        return actual_values

    def program_manual(self, values):
        return self.set_output_settings(values, fresh=True)

    def transition_to_buffered(
            self, device_name, h5file, initial_values, fresh):
        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['/devices/' + device_name]
            if 'static_values' in group:
                data = group['static_values']
                values = {name: data[0][name] for name in data.dtype.names}
            else:
                values = {}
        values = {'dds 0': values}
        return self.set_output_settings(values, fresh=fresh)

    def transition_to_manual(self):
        return True

    def abort_buffered(self):
        return True

    def abort_transition_to_buffered(self):
        return True

    def shutdown(self):
        self.synth.close()
