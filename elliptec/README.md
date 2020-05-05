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
* Copy/paste the `elliptec_unit_conversions.py` file included in this module to the `labscript_suite\labscript_utils\unitconversions\` folder.
  * This is necessary in order to be able to specify positions in real units, e.g. degrees, rather than in units of position encoder counts.

### Testing the Device with the Thorlabs ELLO GUI

Before adding a new Eilliptec device to `connectiontable.py`, it's best to ensure that they are connected and working as desired.
This eliminates some possible issues when debugging if you run into trouble.
The device can be easily tested by opening the ELLO program that is included in the Thorlabs Elliptec Software installation.

In ELLO, select the COM port for your Elliptec interface board (the PCB with a USB connector on one side and a ribbon cable connector on the other), and set the "Search Range" as desired, and click connect.
If you're not sure which COM port corresponds to your interface board, one way to check is to unplug/plug the device and see which COM port appears/disappears from the list.
The search range will look for devices connected to the interface board, which will have an address specified by a 1-digit hex number, `0` to `F`.
There may be multiple devices connected to the interface board, for example when using a ELLB bus distributor or a custom ribbon cable with multiple connections.
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
  * Providing the serial number makes it possible to check that the device at the given address has the specified serial number, ensuring that the correct device is connected.
  Without this it would be easy to mistakenly connect to the wrong device.
  For example, one might accidentally use the correct address but with the wrong interface board.
  Also, the addresses of boards can be changed using the Elliptec API, so including the serial number ensures that connections don't accidentally get swapped if the device addresses change.
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
* If this is the first time that this device is used, trying controlling it via its blacs tab and ensure that the device moves by the instructed amount before using it in a labscript.
  The unit conversion classes defined in this module should have the correct conversion factors, but it's worth double-checking.
  See the "ELL14" part of the "Hardware Quirks" section for some justification on why checking this is important.

## Hardware Quirks

The sections below list quirks of different Elliptec devices.

### ELL14

The ELL14's encoder has a few quirks.

First of all, the encoder has a bit of noise.
That means that if the current position of the device is requested multiple times, it may return multiple different values even if the device hasn't moved.
Fortunately that noise level is quite low, often only differing by one encoder count which corresponds to a few thousandths of a degree.

Also, different ELL14 can have different encoders, which even have different conversions between encoder counts and position in degrees.
Older ELL14 had an encoder where 262,144 counts corresponded to a rotation by 360 degrees.
That encoder stopped being manufactured so Thorlabs had to replace it with a different encoder on newer ELL14, and the new encoder has only 143,360 counts over a 360 degree rotation.

The unit conversion class for the ELL14 is written with the default conversion factor of 143,360 counts per 360 degrees, corresponding to the values for newer ELL14.
If you have an older ELL14 with the old encoder, be sure to adjust the conversion factor appropriately by adding the key/value pair `'slope':262144./360` to the `unit_conversion_parameters` dictionary in the connection table entry for the device.

If you're not sure which encoder your ELL14 has, an easy way to check is to do the following:

1. Open ELLO.
1. Connect to the device.
    * Keep in mind that only one application at a time can connect to the device, so close blacs first if necessary.
1. Expand "Details" section.
1. Multiply the value under "Pulses Per deg" by 360.
    * This value will be slightly off due to rounding errors, but should be close to either 262,144 or 143,360.
1. Make sure to disconnect from the device in ELLO before trying to connect to it again from blacs.

## Generalizing to Other Hardware

The code here was written with the intent that it should be easy to add support for other Elliptec devices.
Below are some required steps to add support for new devices.

* Add a class to `labscript_devices.py` for your device.
  * Your class should inherit from the `ElliptecDevice` class defined in that file and overwrite the appropriate class attributes.
  See the `ELL14` class in that file for an example of how to do that.
* Some devices may need to use additional methods from the Elliptec API.
  To support those, add the required new methods to the `blacs_workers._ElliptecInterface` class.
  See the `_ElliptecInterface.move()` method there for an example on how to write methods like that.
  * See the Elliptec API documentation, or for a list of possible commands.
* To support setting positions with real units, e.g. millimeters or degrees, add a class to `elliptec_unit_conversions.py`.
  * This isn't necessary for some devices, such as the multi-position sliders.
  * If there is a class already present to support the units that you need, you can subclass that class.
    Simply overwrite the default values for the conversion parameters as necessary to match the specifications of your device.
  * See the labscript documentation for more information on how to write unit conversion classes.
  * Make sure to copy/paste our new version of this file to the `labscript_suite\labscript_utils\unitconversions\` folder.

There are many good resources to reference when adding support for a new devices; some are listed below.

* The Elliptec API Manual.
* The manual for your specific Elliptec Device.
* The code, comments, docstrings, and README from this module.
* The labscript documentation.

## FAQ and Common Issues

* Blacs can't connect to the device and throws an error.
  * Try the following:
    1. Read the full error traceback as it will likely tell you exactly what the issue is, which will speed up your debugging.
    1. Ensure that the interface board and Elliptec device are powered on and connected the computer on which blacs is running.
    1. Ensure that the serial number specified for the device in the connection table is correct, and is specified as a string instead of as an integer.
    1. Make sure that no other application, including ELLO, is connected to the interface board, as only one application can connect to it at a time.
    1. As a debugging step, ensure that you can control the device from Ello.
        * Make sure to disconnect from the interface board in the GUI before trying to connect to it again with blacs.
    1. If this it the first time that you've added an Elliptec device to your connection table, also ensure that the required software dependencies are installed (see "Installing Software Dependencies" above).
    1. Sometimes the device doesn't connect on startup but will connect if you reinitialize its blacs tab by clicking on the blue circular arrow at the top right of its tab.
    1. Occasionally restarting the computer, or at least the USB bus can resolve the issue, especially if the last program to interact with the controller didn't exit gracefully.
    1. Click the icon in blacs to display the terminal output for the device.
    Messages to/from the device are printed to that terminal, which may be helpful for debugging.
    See the Elliptec API for instructions on how to understand those messages.
* "Output values set on this device do not match the BLACS front panel" warning
  * This warning can occur for different reasons, and its usually best to just take the value specified by the controller, as that provides the actual position of the actuator.
  Often the error is quite small, frequently just by one encoder count, and can simply be ignored.
  Also, simply setting the output to the desired value will instruct the controller to move to that position, which typically alleviates this warning.
  Below are some reasons why this warning may appear.
    * Often it's just because the actuator tried to move to the desired position and ended up close to, but no exactly at, the desired value.
    In this case it's best to just take the value specified by the controller, or simply ignore the warning.
    When this occurs, the errors are typically pretty small, so unless your system is extremely sensitive, the error typically doesn't matter.
    * For the ELL14 (and possibly other Elliptec devices as well) the encoder has a bit of noise to it.
    In other words multiple calls to read its position may return slightly different values, even if the device hasn't moved at all.
    Since blacs periodically checks in on the device to see what it's position is, often it will return a slightly different value than before and cause this warning to appear spontaneously.
    Again, this error is typically very small and so the warning is likely fine to ignore.
    * This warning may also occur if someone uses the controls on the interface board itself to move the actuator.
    Again in this case one should use the values specified by the device.
    * This may also occur when starting up blacs if the device's position has changed since when blacs was last closed.
    Again in this case one should use the values specified by the device.
