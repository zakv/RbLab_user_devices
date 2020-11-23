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
from labscript import (
    StaticDDS, StaticAnalogOut, StaticDigitalOut, Device, set_passed_properties,
    LabscriptError,
)
import numpy as np


class Agilent83650BOutput(StaticDDS):

    description = "Agilent 83650B Microwave Synthesizer"
    allowed_children = [StaticAnalogOut, StaticDigitalOut]

    @set_passed_properties(
        property_names={
            'connection_table_properties':
                ['ramp_between_frequencies']
        }
    )
    def __init__(self, name, parent_device, ramp_between_frequencies, **kwargs):
        """The output of an Agilent 83650B Microwave Synthesizer.

        Args:
            *args (optional): These arguments will be passed to the `__init__()`
                method of the parent class (StaticDDS).
            **kwargs (optional): Keyword arguments will be passed to the
                `__init__()` method of the parent class (StaticDDS).
        """
        # This code is based on StaticDDS.__init__ but modified to account for
        # the fact that the "gate" doesn't have timing resolution and the fact
        # that the 83650B doesn't have a phase control.

        # We tell Device.__init__ to not call
        # self.parent.add_device(self), we'll do that ourselves later
        # after further intitialisation, so that the parent can see the
        # freq/amp/phase objects and manipulate or check them from within
        # its add_device method.
        Device.__init__(
            self,
            name=name,
            parent_device=parent_device,
            connection='dds 0',
            call_parents_add_device=False,
            **kwargs)

        self.frequency = StaticAnalogOut(
            name=self.name + '_freq',
            parent_device=self,
            connection='freq',
            limits=None,
            # unit_conversion_class=freq_conv_class,  # TODO
            # unit_conversion_parameters=freq_conv_params,
        )
        self.amplitude = StaticAnalogOut(
            name=self.name + '_amp',
            parent_device=self,
            connection='amp',
            limits=None,
            # unit_conversion_class=amp_conv_class,  # TODO
            # unit_conversion_parameters=amp_conv_params,
        )
        self.output_enabled = StaticDigitalOut(
            name=self.name + '_enabled',
            parent_device=self,
            connection='enabled',
        )

        # Now we call the parent's add_device method since we didn't do so
        # earlier in Device.__init__().
        self.parent_device.add_device(self)

    def setphase(self, value, units=None):
        raise LabscriptError("Agilent 83650B does not support phase control.")

    def enable(self):
        """overridden from StaticDDS so as not to provide time resolution -
        output can be enabled or disabled only at the start of the shot"""
        self.output_enabled.go_high()

    def disable(self):
        """overridden from StaticDDS so as not to provide time resolution -
        output can be enabled or disabled only at the start of the shot"""
        self.output_enabled.go_low()


class Agilent83650B(Device):
    allowed_children = [Agilent83650BOutput]

    @set_passed_properties(
        property_names={
            'connection_table_properties':
                ['com_port', 'gpib_address', 'mock']
        }
    )
    def __init__(self, name, com_port, gpib_address, mock=False, **kwargs):
        """An Agilent 83650B connected via a Prologix USB-GPIB converter.

        This labscript device is designed to work with an Agilent 83650B
        microwave synthesizer that is connected to the computer via a Prologix
        USB-GPIB converter. This converter makes the GPIB bus appear as a COM
        port to the computer. No precautions were taken about other devices
        being present on the GPIB bus, so it is best if the Agilent 83650B is
        the only device on the bus.

        To use an Agilent 83650B with this labscript device class code, first
        connect it to the computer via a Prologix USB-GPIB converter. Then add
        an `Agilent83650BOutput` instance to the connection table with an
        instance of this class as its parent device. The output is a
        `StaticDDS`, and supports the `.setamp()`, `.setfreq()`, `.enable()`,
        and `disable()` methods. This synthesizer does NOT provide the ability
        to change the phase of the output, so the `.setphase()` method is NOT
        supported.

        To use an Agilent 83650B without a Prologix USB-GPIB converter, a new
        labscript device must be made. It can inherit almost everything from the
        classes here so it shouldn't be necessary to write a lot of new code.
        The main changes will be in the `_Agilent83650B()` class in
        `blacs_workers.py`, particularly its `_configure_gpib_interface()`
        method. See the code there for more details.

        See the `README.md` in this device's directory for more information.

        Args:
            name (str): The name to give to this Agilent 83650B.
            com_port (str): The COM port, e.g. 'COM1', of the prologix USB-GPIB
                converter used to connect to the Agilent 83650B.
            gpib_address (int): The address of the Agilent 83650B on the GIPB
                bus.
            mock (bool, optional): (Default=False) If set to True then no real
                Agilent 83650B will be used. Instead a dummy that simply prints
                what a real synth would do is used instead. This is helpful for
                testing and development.
            **kwargs: Further keyword arguents are passed to the `__init__()`
                method of the parent class (Device).
        """
        super().__init__(
            name=name,
            parent_device=None,
            connection=None,
            **kwargs,
        )
        self.BLACS_connection = f'{com_port},{gpib_address}'

    def generate_code(self, hdf5_file):
        super().generate_code(hdf5_file)

        output = self.child_devices[0]  # There should only be one child output.

        # Construct data for hdf5 file.
        dtypes = [
            ('freq', np.float64),
            ('amp', np.float64),
            ('gate', np.bool),
        ]
        static_value_table = np.empty(1, dtype=dtypes)
        static_value_table['freq'][0] = output.frequency.static_value
        static_value_table['amp'][0] = output.amplitude.static_value
        static_value_table['gate'][0] = output.output_enabled.static_value

        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('static_values', data=static_value_table)
