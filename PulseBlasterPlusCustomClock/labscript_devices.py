"""Labscript device for RbLab's PulseBlaster Plus! with custom clock

Based on Labscript's pulseblasterUSB.py

We have a "PulseBlaster Plus!", which is outdated and labscript technically
doesn't come with a class for it. Additionally, For some reason our pulseblaster
has a 180 MHz master clock oscillator inside of it instead of the standard 100
MHz that the documentation says it usually has. To get around this, I (Zak) used
PulsePlasterUSB.py to make PulseBlasterPlusCustomClock.py, which is the same
except that the clock frequency set appropriately and the class names have
changed. Additionally, the code was restructed to the "new" register_classes()
format for registering devices with Labscript. This allows us to store the code
in the user_devices section of our git repo (if it were still set up with the
old decorator-style method, the code would have to be stored in the
labscript_devices directory.) So far our PulseBlaster Plus has worked fine
without any further changes to that code.

TODO: Move this info to the README
"""
from labscript_devices.PulseBlaster_No_DDS import PulseBlaster_No_DDS

# Need to know the frequency of the Pulseblaster's internal oscillator
custom_core_clock_freq = 180.0  # MHz


class PulseBlasterPlusCustomClock(PulseBlaster_No_DDS):
    description = 'SpinCore "PulseBlaster Plus!" with Custom 180 MHz Clock Oscillator'
    clock_limit = 8.3e6  # can probably go faster
    # TODO: Update clock resolution, to 2./custom_core_clock_freq
    clock_resolution = 20e-9
    n_flags = 24
    core_clock_freq = custom_core_clock_freq
