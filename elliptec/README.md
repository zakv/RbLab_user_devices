# Thorlabs Elliptec Labscript Integration

## Introduction

This directory contains the code necessary to use Thorlabs Elliptec devices.

The code in this package is primarily based on the Zaber Stage controllers from the official labscript_utils distribution.
In fact, it was started by copy/pasting the files from the Zaber Stage directory, which is why the copyright info was retained.
Additionally, the approach to the low-level communication with the drivers was informed by the script in this <https://github.com/cdbaird/TL-rotation-control> repo.

The goal of this package is not to replace the ELLO GUI program that is available from Thorlabs as part of the Elliptec Software download.
It is only intended to control the positions of Elliptec devices from labscript.
There are additional things that the devices can do, such as find their motor
resonance frequencies and clean off their track.
Those features can be controlled using ELLO and there's really no need to control them from blacs directly.

This package was developed and tested on Windows, but it may work on other operating systems as well.
As of this writing, the Elliptec Software package from Thorlabs is only available for Windows.
However, the device communication in this module is done entirely via low-level serial port commands, so it should work on any operating system that is compatible with pyvisa.

## Supported Hardware

As of this writing, this package only supports the ELL14.
However, it was written in such a way that it should be straightforward to generalize it to work with other devices as well.
See "Generalizing to Other Hardware" below for more information on that.

Supported Hardware List:

* ELL14 Rotation Mount

## Setup

Before using this module with Labscript, some additional setup is required.
The steps are listed here and subsections below provide additional information about each step.

* Install the software dependencies.
* Test the device with the Thorlabs ELLO GUI.

### Installing Software Dependencies

The following software needs to be installed in order to use this module:

* Python 3 (Python 2 isn't supported)
* Thorlabs Elliptec Software, available for free from their website.
  * This may not be completely necessary (and is only available on Windows as of this writing) but it is helpful for debugging and allows for additional controls for features not used by this module.
* pyvisa
  * To install via pip: `pip install pyvisa`
  * If you do not have a VISA implementation installed, you may need to install one as well.
    See the pyvisa installation instructions for more information.
* Copy/paste the `elliptec_unit_conversions.py` file included in this module to the  `labscript_suite\labscript_utils\unitconversions\` folder.
  * This is necessary in order to be able to specify positions in real units, e.g. degrees, rather than in units of position encoder counts.

### Testing the Device with the Thorlabs ELLO GUI

Before adding a new Eilliptec device to `connectiontable.py`, it's best to ensure that they are connected and working as desired.
This eliminates some possible issues when debugging if you run into trouble.
The device can be easily tested by opening the ELLO program that is included in the Thorlabs Elliptec Software installation.

In ELLO, select the COM port for your Elliptec interface board (the PCB with a USB connector on one side and a ribbon cable connector on the other), and set the "Search Range" as desired, and click connect.
If you're not sure which COM port corresponds to your interface board, one way to check is to unplug/plug the device and see which COM port appears/disappears from the list.
The search range will look for devices connected to the interface board, which will have an address specified by a 1-digit hex number, `0` to `F`.
There may be multiple devices connected to the interface board if a ELLB bus distributor is used.
Take note of the COM port and the address as these will be needed later.

This may seem a little confusing, but the COM port and address are different.
Basically, the COM port specifies where the interface board is connected to your computer (via USB), and the address specifies which device connected to a given interface board (via ribbon cable) you're trying to control.

After connecting to the device, ensure that you can move it using the controls provided.
If so, you're in good shape.
While you have ELLO open and connected to your device, expand the "Details" section and take note of the serial number as you'll need to know that as well.

Once you are done testing out the device, make sure to click the disconnect button.
Only one application at a time (at least one Windows) can connect to the device, so you'll have to disconnect from in in ELLO before connecting to it with blacs.

## Example Usage

### Typical Connection Table Entry

Below is an example of how include a controller and actuator in `connectiontable.py`.

```python
# Import the devices.
from userlib.user_devices.RbLab.elliptec.labscript_devices import ElliptecInterfaceBoard, ELL14
# Import the unit converter.
from userlib.user_devices.RbLab.elliptec.elliptec_unit_conversions import ELL14_Unit_Converter

# Instantiate a interface board.
y_northward_waveplate_interface_board = ElliptecInterfaceBoard(
    name='y_northward_waveplate_interface_board',
    com_port='COM6',
    mock=False,
)
# Instantiate a actuator.
y_northward_waveplate = ELL14(
    name='y_northward_waveplate',
    parent_device=y_northward_waveplate_interface_board,
    connection='0',
    serial_number='11400101',
    unit_conversion_class=ELL14_Unit_Converter,
    unit_conversion_parameters={'offset': 0.0},
)
```

Some additional notes on the arguments are provided below.

* More information about most of these arguments can be found in the docstrings for the classes.
Those can be accessed using introspection in an interactive python session or can be manually located in the `labscript_devices.py` file in this directory.
* Note that you must instantiate an interface board instance, then add any Elliptec devices as child devices of that board.
* It is possible to create a mock interface board by setting `mock=True` in its instantiation.
  Any device that is connected to it will also be simulated and will have serial number `12345678`.
  This is useful for testing/development purposes.
* The value for `connection` argument during the actuator instantiation must be the address of the Elliptec device.
  * This is a single digit hex number in the range `0` to `F`.
    See the "Testing the Device with the Thorlabs ELLO GUI" section above for details on how to find it.
  * Note that the value for `connection` should be provided as a string.
* The `serial_number` should be specified as a string, and can be checked with ELLO.
  It is required here because the addresses of Elliptec devices can be changed in ELLO.
  Providing the serial number makes it possible to check that the device at the given address has the specified serial number, ensuring that the correct device is connected.
* The unit conversion class is used to convert back and forth between "base units" (i.e. position encoder counts) and real units, e.g. degrees or mm.
  * Of course make sure to specify the correct conversion class for your device.
  * Also, make sure that the `elliptec_unit_conversions.py` file has been copy/pasted into the l`abscript_suite\labscript_utils\unitconversions\` folder, as mentioned in the "Installing Software Dependencies" section above.
  * The default parameters for the conversion class are set in `elliptec_unit_conversions.py` but can be adjusted by specifying their values in the connection table.
    For example, you may find it useful to adjust the value for `'offset'` for rotation mounts holding waveplates such that the waveplate axis is vertical when the position is set to 0 degrees, even though that may not be the position corresponding to position encoder count zero.
* As is standard with the labscript connection table, the `y_northward_waveplate =` part isn't necessary.
It is sufficient (and necessary) to simply provide the `name` argument.

### Usage in a Labscript

Because only static outputs are supported, the usage is fairly straightforward.
An example is provided below.

```python
# Move actuator to its desired position.
y_northward_waveplate.constant(
        actuator_position_y_northward_waveplate,
        units='deg',
    )
```

* Note that the object used is the instance of the actuator device class, not the instance of the interface board class.
* Since the output is static, no value for `time` is passed to `.constant()`.
* Here it is assumed that there is a global called `actuator_position_y_northward_waveplate` defined.
* Note that the units are specified to be in `'deg'` instead of base units, which are position encoder counts.
  It is also possible to specify the units as `'counts'` if desired, which is the default value.

## Generalizing to Other Hardware

TODO

Initially this code was developed to be very general and compatible with a wide range of Thorlabs actuators.
However it quickly became clear that I was not familiar enough with the similarities and differences between the wide array of their motion control projects, so I decided to take a bottom-up approach.
Instead of writing the most general code, I wrote code specific to static outputs with the KDC101 and plan to generalize it as necessary.

When generalizing the code, it's important to have good resources.
A lot of helpful information, including example C# code for various pieces of hardware, is provided in the Kinesis help files.
These can be accessed by opening the `Thorlabs.MotionControl.DotNet_API.chm` help file in the Kinesis directory.
The process for using the .NET code in python is relatively straightforward and is explained in the pythonnet documentation, and a specific example of using it with the Kinesis .NET API is available in the github repo mentioned in the introduction.
Additionally, the code in the KDC101 `blacs_workers.py` should be a useful reference.

## FAQ and Common Issues

TODO

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
