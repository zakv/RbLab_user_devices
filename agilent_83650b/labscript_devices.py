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
import warnings

import numpy as np

from labscript import (
    StaticDDS, StaticAnalogOut, StaticDigitalOut, Device, set_passed_properties,
    LabscriptError,
)
from labscript_utils import dedent
from ._hardware_capabilities import agilent_83650b
from .frequency_converter import FrequencyConverter


class Agilent83650BOutput(StaticDDS):

    description = "Agilent 83650B Microwave Synthesizer"
    allowed_children = [StaticAnalogOut, StaticDigitalOut]

    @set_passed_properties(
        property_names={
            'connection_table_properties':
                [
                    'frequency_limits',
                    'power_limits',
                    'ramp_between_frequencies',
                    'ramp_step_size',
                    'ramp_min_step_duration',
                ]
        }
    )
    def __init__(self, name, parent_device, frequency_limits=None,
                 power_limits=None, frequency_conversion_class=None,
                 frequency_conversion_params=None, power_conversion_class=None,
                 power_conversion_params=None, ramp_between_frequencies=False,
                 ramp_step_size=None, ramp_min_step_duration=None, **kwargs):
        """The output of an Agilent 83650B Microwave Synthesizer.

        See the `README.md` in the directory containing this file for more
        information including example connection table entries and example
        commands that can be run in a labscript.

        Args:
            name (str): The name for the output, used when setting the
                amplitude, etc. in a labscript.
            parent_device (Agilenth83650B): The instance of the `Agilent83650B`
                for which this is the output.
            frequency_limits (tuple of two floats, optional): (Default=`None`)
                The minimum and maximum frequency respectively to allow for the
                output. If set to a value outside of the hardware limits of the
                device, a warning will be printed and the values will be coerced
                to the device's achievable range. This argument can be used to
                restrict the output frequency to a range smaller than that
                achievable by the hardware. If set to `None` then the frequency
                limits will be set equal to the hardware limits, giving the
                output its maximum possible range.
            power_limits (tuple of two floats, optional): (Default=`None`) The
                minimum and maximum power respectively to allow for the output.
                If set to a value outside of the hardware limits of the device,
                a warning will be printed and the values will be coerced to the
                device's achievable range. This argument can be used to restrict
                the output power to a range smaller than that achievable by the
                hardware. If set to `None` then the power limits will be set
                equal to the hardware limits, giving the output its maximum
                possible range.
            frequency_conversion_class (UnitConversion, optional):
                (Default=`None`) The conversion class to use for the frequency,
                which makes it possible to set the output in units other than
                the base units, which are Hz. If set to `None` then the
                `FrequencyConverter` class from `frequency_converter.py` in the
                same directory as this file will be used.
            frequency_conversion_params (dict, optional): (Default=`None`)
                Arguments to pass to the `frequency_conversion_class` during its
                initialization.
            power_conversion_class (UnitConversion, optional): (Default=`None`)
                The conversion class to use for the output power, which makes it
                possible to set the output in units other than the base unit,
                which is dBm. If set to `None`, then no unit conversion class
                will be used.
            power_conversion_params (dict, optional): (Default=`None`) Arguments
                to pass to the `power_conversion_class` during its
                initialization.
            ramp_between_frequencies (bool, optional): (Default=`False`) If
                `False`, then whenever the output frequency is instructed to
                change, it will discretely jump to the new frequency. If set to
                `True`, the the output will instead ramp to the new values. This
                can be useful for example if suddenly jumping the frequency may
                throw a laser out of lock.
            ramp_step_size (float, optional): (Default=`None`) The size of the
                frequency steps to use when ramping the output frequency. This
                only has an effect if `ramp_between_frequencies` is set to
                `True`. If `ramp_between_frequencies` is set to `True` then a
                value for `ramp_step_size` must be provided, otherwise a
                `ValueError` will be raised.
            ramp_min_step_duration ([type], optional): (Default=`None`) The
                minimum amount of time to stay at one frequency before moving to
                the next during a frequency ramp of the output. This only has an
                effect if `ramp_between_frequencies` is set to `True`. The
                actual amount of time spent at any given output frequency may be
                longer due to the amount of time it takes for the output
                frequency to change .If `ramp_between_frequencies` is set to
                `True` then a value for `ramp_min_step_duration` must be
                provided, otherwise a `ValueError` will be raised.
            **kwargs (optional): Additional keyword arguments will be passed to
                `Device.__init__()`.

        Raises:
            ValueError: A `ValueError` is raised if `ramp_between_frequencies`
                is `True` but no value is provided for `ramp_step_size`.
            ValueError: A `ValueError` is raised if `ramp_between_frequencies`
                is `True` but no value is provided for `ramp_min_step_duration`.
        """
        # Coerce any provided limits to be within the hardware limits
        self.frequency_limits = self._coerce_set_frequency_limits(
            frequency_limits,
        )
        self.power_limits = self._coerce_set_power_limits(power_limits)

        # Ensure settings are valid.
        if ramp_between_frequencies:
            if not ramp_step_size:
                msg = """A value for ramp_step_size must be provided if
                ramp_between_frequencies is True."""
                raise ValueError(dedent(msg))
            if not ramp_min_step_duration:
                msg = """A value for ramp_min_step_duration must be provided if
                ramp_between_frequencies is True."""
                raise ValueError(dedent(msg))

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
            **kwargs,
        )

        # Ask the parent device if it has default unit conversion classes it
        # would like us to use:
        if hasattr(parent_device, 'get_default_unit_conversion_classes'):
            classes = parent_device.get_default_unit_conversion_classes(self)
            default_frequency_conversion, default_power_conversion_class = classes
            # If the user has not overridden, use these defaults. If
            # the parent does not have a default for one or more of amp,
            # freq or phase, it should return None for them.
            if frequency_conversion_class is None:
                frequency_conversion_class = default_frequency_conversion
            if power_conversion_class is None:
                power_conversion_class = default_power_conversion_class

        self.frequency = StaticAnalogOut(
            name=self.name + '_freq',
            parent_device=self,
            connection='freq',
            limits=self.frequency_limits,
            unit_conversion_class=frequency_conversion_class,
            unit_conversion_parameters=frequency_conversion_params,
        )
        self.amplitude = StaticAnalogOut(
            name=self.name + '_amp',
            parent_device=self,
            connection='amp',
            limits=self.power_limits,
            unit_conversion_class=power_conversion_class,
            unit_conversion_parameters=power_conversion_params,
        )
        self.output_enabled = StaticDigitalOut(
            name=self.name + '_enabled',
            parent_device=self,
            connection='enabled',
        )

        # Now we call the parent's add_device method since we didn't do so
        # earlier in Device.__init__().
        self.parent_device.add_device(self)

    def _coerce_set_frequency_limits(self, frequency_limits):
        hardware_min = agilent_83650b['freq']['min']
        hardware_max = agilent_83650b['freq']['max']
        units = agilent_83650b['freq']['base_unit']
        if frequency_limits:
            set_min, set_max = frequency_limits
            if set_min > hardware_min:
                final_min = set_min
            else:
                msg = f"""Frequency minimum was set to {set_min} {units} but
                    the hardware limit is {hardware_min} {units}. Coercing
                    the set limit to be within hardware limits."""
                warnings.warn(dedent(msg))
                final_min = hardware_min
            if set_max < hardware_max:
                final_max = set_max
            else:
                msg = f"""Frequency maximum was set to {set_max} {units} but
                    the hardware limit is {hardware_max} {units}. Coercing
                    the set limit to be within hardware limits."""
                warnings.warn(dedent(msg))
                final_max = hardware_max
            frequency_limits = (final_min, final_max)
        else:
            frequency_limits = (hardware_min, hardware_max)
        return frequency_limits

    def _coerce_set_power_limits(self, power_limits):
        hardware_min = agilent_83650b['amp']['min']
        hardware_max = agilent_83650b['amp']['max']
        units = agilent_83650b['amp']['base_unit']
        if power_limits:
            set_min, set_max = power_limits
            if set_min > hardware_min:
                final_min = set_min
            else:
                msg = f"""Power minimum was set to {set_min} {units} but the
                    hardware limit is {hardware_min} {units}. Coercing the set
                    limit to be within hardware limits."""
                warnings.warn(dedent(msg))
                final_min = hardware_min
            if set_max < hardware_max:
                final_max = set_max
            else:
                msg = f"""Power maximum was set to {set_max} {units} but the
                    hardware limit is {hardware_max} {units}. Coercing the set
                    limit to be within hardware limits."""
                warnings.warn(dedent(msg))
                final_max = hardware_max
            power_limits = (final_min, final_max)
        else:
            power_limits = (hardware_min, hardware_max)
        return power_limits

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
            com_port (str): The COM port, e.g. `'COM1'`, of the prologix
                USB-GPIB converter used to connect to the Agilent 83650B.
            gpib_address (int): The address of the Agilent 83650B on the GPIB
                bus.
            mock (bool, optional): (Default=`False`) If set to `True` then no
                real Agilent 83650B will be used. Instead a dummy that simply
                prints what a real synth would do is used instead. This is
                helpful for testing and development.
            **kwargs: Further keyword arguents are passed to the `__init__()`
                method of the parent class (`Device`).
        """
        super().__init__(
            name=name,
            parent_device=None,
            connection=None,
            **kwargs,
        )
        self.BLACS_connection = f'{com_port},GPIB{gpib_address}'

    def get_default_unit_conversion_classes(self, device):
        """Get default unit converters for outputs.

        Child devices call this during their `__init__()` (with themselves as
        the argument) to check if there are certain unit calibration classes
        that they should apply to their outputs, if the user has not otherwise
        specified a calibration class.

        This method was taken from NovaTechDDS9M.py's NovaTechDDS9M class's
        implementation of this method. Returned converters are for frequency and
        power respectively.
        """
        return FrequencyConverter, None

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
