"""Labscript device for RbLab's PulseBlaster Plus! with custom clock

Based on Labscript's pulseblasterUSB.py. See README in this directory for more
information.
"""
from labscript_devices.PulseBlaster_No_DDS import PulseBlaster_No_DDS

# Need to know the frequency of the Pulseblaster's internal oscillator
CUSTOM_CORE_CLOCK_FREQ = 180.0  # MHz


class PulseBlasterPlusCustomClock(PulseBlaster_No_DDS):
    description = 'SpinCore "PulseBlaster Plus!" with Custom 180 MHz Clock Oscillator'
    clock_limit = 8.3e6  # can probably go faster
    # TODO: Update clock resolution, to 2./CUSTOM_CORE_CLOCK_FREQ
    clock_resolution = 20e-9
    n_flags = 24
    core_clock_freq = CUSTOM_CORE_CLOCK_FREQ
