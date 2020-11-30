# Agilent 83650B

## Introduction

This directory contains the code necessary to use an Agilent 83650B connected to a computer via a Prologix USB-GPIB converter.
As such the code is not very general; it requires fairly specific hardware.
See if the "Using a Different GPIB Interface" section below for instructions on using a different GPIB interface.

This package was developed and tested on Windows, but should work on other operating systems as well.

## Features

* Control the frequency and amplitude of an Agilent 83650B output.
* Toggle the output on/off.
* Ramp, rather than jump, between output frequencies.
  * This can be helpful e.g. if jumping the frequency would throw a laser out of lock.
  * The ramps are software timed and can be a bit slow, see the "Frequency Ramps" section below for more information.
* Included unit conversion module for specifying frequencies in Hz, MHz, or GHz, which is enabled by default.
* Supports remote value checking.
  * This means that blacs can detect if the output settings are changed by another program or by a user interacting with the physical device.
* Supports smart programming.
  * If the output settings are already at their desired values when a shot is run, they aren't reprogrammed.
    This can greatly reduce the amount of time required to transition to buffered when running a shot.
* Supports hardware mocking.
  * It is possible to simulate a device, even without having a real one, by setting `mock=True` in the connection table.

## Required Hardware

The hardware communication commands used in this device assume that the Agilent 83650B is connected to the computer via a Prologix USB-GPIB converter, so the required hardware components are:

* Agilent 83650B
* Prologix USB-GPIB converter

### Using a Different GPIB Interface

To use an Agilent 83650B without a Prologix USB-GPIB converter, a new labscript device must be made.
It can inherit almost everything from the classes here so it shouldn't be necessary to write a lot of new code.
The main changes will be in the `_Agilent83650B()` class in `blacs_workers.py`, particularly its `_configure_gpib_interface()`, `write()`, `query()` and `read()` methods.
See the code there for more details.

## Software Dependencies

The following software needs to be installed in order to use this module:

* Python 3 (Python 2 isn't supported)
* `pyvisa`, a python package for communicating with VISA instruments.
  * Can be installed via `pip` or `conda`.

## Example Usage

### Typical Connection Table Entry

Below is an example of how to add an Agilent 83650B to the `connectiontable.py`.
This requires adding two entries, one for the Agilent 83650B itself and one for its output.

```python
# Import the required classes.
from user_devices.RbLab.agilent_83650b.labscript_devices import Agilent83650B, Agilent83650BOutput

# Instantiate an Agilent8350B.
Agilent83650B(
    name='microwave_synthesizer',
    com_port='COM1',
    gpib_address=19,
    mock=False,
)

# Instantiate the output for the Agilent 8350B.
Agilent83650BOutput(
    name='microwave_synthesizer_output',
    parent_device=microwave_synthesizer,
    ramp_between_frequencies=True,
    ramp_step_size=10e6,  # Ramp in 10 MHz steps.
    ramp_min_step_duration=10e-3,  # Stay at least 10 ms at each output frequency.
)
```

Some additional notes on the arguments are provided below.

* More information about most of these arguments can be found in the docstrings for the classes.
Those can be accessed using introspection in an interactive python session or can be manually located in the `labscript_devices.py` file in this directory.

### Usage in a Labscript

Because only static outputs are supported, the usage is fairly straightforward.
An example is provided below.

```python
# Enable or disable the output of the device (only do one!).
microwave_synthesizer_output.enable()
# microwave_synthesizer_output.disable()

# Set the output frequency (base unit is Hz). This sets it to 500 MHz.
microwave_synthesizer_output.setfreq(500, units='MHz')

# Set the output power (base unit is dBm). This sets it to -5 dBm.
microwave_synthesizer_output.setamp(-5)
```

* Note that the instance of the `Agilent83650BOutput` class is used; not the `Agilent83650B` instance.
* Since the output is static, no value for `time` is passed to any of these methods.

## Other Notes

### Frequency Ramps

Due to some apparent hardware limitations, the frequency ramps are actually software timed and can take a while if many steps are needed.
The Agilent 83650B does support hardware timed sweeps, but the output frequency always immediately resets to the initial ramp frequency once the ramp has finished.
This has the unfortunate downside that the ramp rate isn't very fast or well-controlled.
An upper limit on the ramping rate can be set with the optional `ramp_step_size` and `ramp_min_step_duration` arguments of the `Agilent83650BOutput` class.

The ramps can take a while to complete.
Therefore when scanning the output frequency and other parameters with runmanager, it is best to make output frequency be the outermost loop.
That makes the output frequency change less often, which can greatly reduce the amount of time spent changing the output frequency.
This is particularly true given that this device supports smart programming so no commands at all are sent if the output is already configured correctly for the upcoming shot.

### Local Lockout

When the Agilent 83650B receives a command over the GPIB bus, it locks the front panel of the synthesizer.
That means that it will ignore button presses on the device itself so that e.g. the frequency can't be changed manually.
To allow manual operation again, press the "LOCAL" button on the device, which will make the synthesizer respond to button presses on its front panel again.

Note that because this code supports remote value checks, it will poll the device's current settings periodically.
Each time the settings are polled, commands are sent over the GPIB bus, which locks the synthesizer's front panel again.
To allow manual operation for extended periods without needing to frequently press the "LOCAL" button, be sure to close blacs to prevent it from polling the device's settings periodically.
