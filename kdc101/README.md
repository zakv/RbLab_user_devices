# KDC101

## Introduction

This directory contains the code necessary to use a Thorlabs KDC101 brushed DC servo motor controller.
The KDC101 is capable of controlling various pieces of hardware.
As of this writing, these pieces of hardware are typically actuated by the Z8 series of brushed DC servo motors, such as the Z812.

Furthermore, "sequences" of moves do not currently have built-in support.
In other words, this package allows setting the position of actuators before the start of a shot, but doesn't not support programming the devices to move mid-sequence when triggered.
It may still be possible to do this by adjusting the controller's settings in the Kinesis GUI and then manually configuring a digital output channel to trigger it.
However programmatically configuring those moves is not supported here, though the package could be generalized to do so.

The code in this package is primarily based on the Zaber Stage controllers from the official labscript_utils distribution.
In fact, it was started by copy/pasting the files from the Zaber Stage directory, which is why the copyright info was retained.
Additionally, the approach to the low-level communication with the drivers was informed by the script in this <https://github.com/trautsned/thorlabs_kenesis_python> repo.

This package was developed and tested on Windows, but should work on other operating systems as well.

## Supported Hardware

As of this writing, this package only supports the KDC101 and some of the devices that it can control.
The code should be relatively easy to generalize and may even work for other hardware, potentially without modification.
This is particularly true for the actuators.
Though not tested, it's likely that the `BrushedDCServoMotor` class here will work for most hardware that is compatible with the KDC101.

* Supported Controllers:
  * KDC101 Brushed DC Servo Motor Controller.
* Supported Actuators:
  * Z812 Brushed DC Servo Motor Actuator.
  * Likely most of the other actuators that are compatible with the KDC101.
    * For these either create a new class in `labscript_devices.py` or use the generic `BrushedDCServoMotor` class.

## Setup

Before using this module with Labscript, some additional setup is required.
The steps are listed here and subsections below provide additional information about each step.

* Install the software dependencies.
* Test the device with the Thorlabs Kinesis GUI.

### Installing Software Dependencies

The following software needs to be installed in order to use this module:

* Python 3 (Python 2 isn't supported)
* Thorlabs Kinesis, available for free from their website.
  * Take a note of the install directory when installing, as you will need to know it later on.
* pythonnet, a python package for interfacing between python and the .NET framework.
  * To install via pip: `pip install pythonnet`

### Testing Device and Connection

Before adding a new controller and actuator to `connectiontable.py`, it's best to ensure that they are connected and working as desired.
This eliminates some possible issues when debugging if you run into trouble.
The controller and actuator can be easily tested by opening the Thorlabs Kinesis GUI.
Then simply ensure that you can connect to the controller and move the actuator.
You may also want to home the actuator while you have the GUI open.

Importantly, make sure to disconnect from the controller in the Kinesis GUI before trying to connect to it with blacs, as only one application can connect to a controller at a time.
This can be done by "unloading" the controller in the Kinesis GUI, or by closing the program entirely.

## Homing

To ensure that the actuator positioning is repeatable, even if the device is power cycled, the code here makes sure that the device is homed when its blacs tab is started.
Once the device is homed, either by the code here or using the Kinesis GUI, it will stay homed until it is power cycled.

If the device is not homed when its blacs tab is started, one of two things will occur depending on whether the controller was instantiated with `allow_homing=True` or `allow_homing=False`.
If `allow_homing` is set to `True`, then the device will automatically be homed.
On the other hand, if `allow_homing` is set to `False`, then the code will raise a `RuntimeError` and the device will not initialized.

This control is provided because the actuator will move to near the end of its range when homing.
That could be a problem if e.g. the actuator steers a high power beam which could be sent into an unsafe direction during homing.
In that case it is best to instantiate the controller with `allow_homing=False`, then perform the homing using the Kinesis GUI after ensuring that it is safe to do so by e.g. turning off or blocking the high power light source.

## Example Usage

### Typical Connection Table Entry

Below is an example of how include a controller and actuator in `connectiontable.py`.

```python
# Import the devices.
from user_devices.RbLab.kdc101.labscript_devices import KDC101, Z812

# Instantiate a controller.
pump_795_vertical_actuator_controller = KDC101(
    name='pump_795_vertical_actuator_controller',
    serial_number=27255743,
    allow_homing=False,
    mock=False,
    kinesis_path=r'C:\Program Files\Thorlabs\Kinesis',
)
# Instantiate a actuator.
pump_795_vertical_actuator = Z812(
    name='pump_795_vertical_actuator',
    limits=(0, 12),
    parent_device=pump_795_vertical_actuator_controller,
    connection='1',
)
```

Some additional notes on the arguments are provided below.

* More information about most of these arguments can be found in the docstrings for the classes.
Those can be accessed using introspection in an interactive python session or can be manually located in the `labscript_devices.py` file in this directory.
* In order for the code here to work, it needs to be able to access the Kinesis .NET libraries for interacting with the hardware.
  * Since the location of these libraries can vary from system to system, the user must provide the path to them as the kinesis_path argument when instantiating an instance of the controller class in `connectiontable.py`.
  * The standard install directory for these libraries is `C:\Program Files\Thorlabs\Kinesis`, though again the location may vary on your system.
  * The `kinesis_path` is written using a raw string so that the python interpreter doesn't mistake those backslashes as escape characters, hench the `r` prefix.
Alternatively, forward slashes can be used or the backslashes can be escaped.
* The value for `connection` argument during the actuator instantiation doesn't have any effect, but a value must be provided.
* As is standard with the labscript connection table, the `pump_795_vertical_actuator =` part isn't necessary.
It is sufficient (and necessary) to simply provide the `name` argument.

### Usage in a Labscript

Because only static outputs are supported, the usage is fairly straightforward.
An example is provided below.

```python
# Move actuator to its desired position.
pump_795_vertical_actuator.constant(actuator_position_pump_795_vertical)
```

* Note that the object used is the instance of the `Z812` actuator class, not the instance of the `KDC101` controller class.
* Since the output is static, no value for `time` is passed to `.constant()`.
* Here it is assumed that there is a global called `actuator_position_pump_795_vertical` defined.

## Generalizing to Other Hardware

Initially this code was developed to be very general and compatible with a wide range of Thorlabs actuators.
However it quickly became clear that I was not familiar enough with the similarities and differences between the wide array of their motion control projects, so I decided to take a bottom-up approach.
Instead of writing the most general code, I wrote code specific to static outputs with the KDC101 and plan to generalize it as necessary.

When generalizing the code, it's important to have good resources.
A lot of helpful information, including example C# code for various pieces of hardware, is provided in the Kinesis help files.
These can be accessed by opening the `Thorlabs.MotionControl.DotNet_API.chm` help file in the Kinesis directory.
The process for using the .NET code in python is relatively straightforward and is explained in the pythonnet documentation, and a specific example of using it with the Kinesis .NET API is available in the github repo mentioned in the introduction.
Additionally, the code in the KDC101 `blacs_workers.py` should be a useful reference.

## FAQ and Common Issues

* Blacs can't connect to the controller and throws an error.
  * Try the following:
    1. Read the full error traceback as it will likely tell you exactly what the issue is, which will speed up your debugging.
    1. Ensure that the controller is powered on and plugged into the computer on which blacs is running.
    1. Ensure that the serial number specified for the device in the connection table is correct.
    1. Ensure that you've provided the correct path to the Kinesis folder in the `kinesis_path` argument in the connection table entry for the controller.
    1. Make sure that no other application, including the Kinesis GUI, is connected to the device, as only one application can connect to it at a time.
    1. As a debugging step, ensure that you can control the device from the Kinesis GUI.
        * Make sure to disconnect from (aka "unload") the controller in the GUI before trying to connect to it again with blacs.
    1. If this it the first time that you've added a KDC101 to your connection table, also ensure that the required software dependencies are installed (see "Installing Software Dependencies" above).
    1. Sometimes the device doesn't connect on startup but will connect if you reinitialize its blacs tab by clicking on the blue circular arrow at the top right of its tab.
    1. Occasionally restarting the computer, or at least the USB bus can resolve the issue, especially if the last program to interact with the controller didn't exit gracefully.
    1. If the controller was created with `allow_homing=False` and the device isn't homed when the its blacs tab is initialized then it will throw a `RuntimeError`.
    In this case the user must home the device using the Kinesis GUI.
    Of course make sure it is safe to do so by blocking any relevant high power beams or doing anything else necessary before homing the device.
* "Output values set on this device do not match the BLACS front panel" warning
  * This warning can occur for different reasons, and its usually best to just take the value specified by the controller, as that provides the actual position of the actuator.
  Also, simply setting the output to the desired value will instruct the controller to move to that position, which typically alleviates this warning.
  Below are some reasons why this warning may appear.
    * Often it's just because the actuator tried to move to the desired position and ended up close to, but no exactly at, the desired value.
    In this case it's best to just take the value specified by the controller.
    When this occurs, the errors are typically less than 1 um, so unless your system is extremely sensitive, the error typically doesn't matter.
    Also, sometimes the servo will settle to the correct value a few seconds after this warning was issued.
    * This warning may also occur if someone uses the controls on the KDC101 itself to move the actuator.
    Again in this case one should use the values specified by the controller.
    * This may also occur when starting up blacs if the device's position has changed since when blacs was last closed.
