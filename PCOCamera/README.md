# PCOCamera README

## Introduction

This Labscript device module is intended to work with PCO cameras.
Most of its classes inherit from the corresponding classes of IMAQdxCamera, which is how most of the interfacing with BLACS and Labscript is performed.
Communication with the camera is done through PCO's SDK.
The SDK's functions are wrapped with python using the python package Instrumental, which in turn uses the python packages NiceLib and CFFI.

## Supported Models

During development, this module was tested with a PCO Pixelfly USB and the PCO SDK v1.24 on a Windows 10 machine.
It is intended to be compatible with other camera models from PCO that use the PCO SDK, but they have not been tested.
If you try out a different camera model, let us know if it works or if you run into issues!
Note that not all functions in the PCO SDK are supported by all cameras, so e.g. setting a value for `IRSensitivity` in the connection table's `camera_attributes` will cause a camera to throw an error if it doesn't support the `PCO_SetIRSensitivity` command.
See the PCO SDK's manual for a list of compatible camera models for each command.

### Known Compatible Models

* PCO Pixelfly USB

## Setup

Before using this module with Labscript, some additional setup is required.
The subsections below list the required an suggested steps.

### Software Dependencies

In addition to the Labscript suite, the following software needs to be installed in order to use this module:

* Python 3 (Python 2 isn't supported)
* The PCO SDK
* The PCO Interface driver for the camera's interface type (e.g. USB)
* Instrumental
  * To install via pip: `pip install Instrumental-lib`
* NiceLib
  * To install via pip: `pip install NiceLib`

### Add Camera Library to PATH

The compiled functions for interfacing with PCO cameras are stored in a library called S2C_Cam.dll.
In order for Instrumental to access that library, its path must be added to the list of folders stored in the system's Path environment variable.
The path to S2C_Cam.dll will depend on the install location of the PCO SDK, but the default for a system-wide install is `C:\Program Files (x86)\Digital Camera Toolbox\pco.sdk\bin64`.
Note that this is the path to the 64 bit library.
If your system is running 32 bit Python, use the S2C_Cam.dll in the `bin` folder rather than the `bin64` folder.

To edit the Path variable on Windows 10, do the following:

1. Press <kbd>Win</kbd>+<kbd>r</kbd>
2. Type `SystemPropertiesAdvanced` and hit <kbd>enter</kbd>
3. Click `Environment Variables...`
4. Select `Path` and click `Edit...`
    * The `Path` variable either for the current user or the system-wide one can be used.
    Using the system-wide one will edit `Path` for all users.
5. Click `New` and enter the path to S2C_Cam.dll with the proper bitness for your Python installation.
6. Click `Ok` on all of the `System Properties` windows to accept the edited settings and close the windows.

### Running Setup Scripts

Although not strictly necessary, the following steps may improve your experience with this module:

* To prevent the files `lextab.py` and `yacctab.py` from being created in the python's working directory, follow the instructions listed in [issue #91](https://github.com/mabuchilab/Instrumental/issues/91) on Instrumental's Github issue tracker.
These files don't cause any issues, but it can be annoying to have them littering your working directory.
* When an error occurs in the PCO SDK, an error code is returned.
Instrumental includes C source code for function to convert the error code into helpful human-readable text, but it must be compiled.
To do so, follow the instructions listed in [issue #30](https://github.com/mabuchilab/Instrumental/issues/30) on Instrumental's Github issue tracker.
To compile the code, a C compiler is necessary (on Windows "Microsoft Visual Studio C++ Build Tools" will do the job).
If that code isn't compiled, the error code will simply be returned to the user with instructions on how to look up its meaning manually.

## Additional Tips

* The PCO SDK's built-in logging can be enabled by creating a blank text file called `C:\ProgramData\pco\SC2_Cam.log`, which can be helpful when debugging.
Logging can significantly slow down performance however, so delete, move, or rename the log file when done debugging.

## Known Issues/Limitations

* Not all of the functions in the PCO SDK have been wrapped.
If you need access to any additional PCO SDK functions, let us know.
* The files `lextab.py` and `yacctab.py` can sometimes be created in your working directory.
This isn't intrinsically an issue, but can be annoying.
For a workaround, see the "Running Setup Scripts" section above.
* In order to automatically convert error codes from the PCO SDK into human-readable strings some C code in Instrumental must be compiled.
See the "Running Setup Scripts" section above for additional information.
* The setting for TriggerMode is ignored when the camera is in manual_mode.
Instead it is set to the correct mode for triggering from software automatically.
* Hardware ROI is not yet supported because not all PCO cameras support it, however software ROI is implemented.
The only downside of Software ROI relative to Hardware ROI is that it is somewhat inefficient because it still runs unused pixels through the camera's ADC and transfers the data into memory, which leads to somewhat slower processing and video framerates.
* The 'visibility level' of attributes is not implemented.
All attributes are returned for all visibility levels.
* There are some references to IMAQdx, NI MAX, etc. in the window that pops up when "Attributes" is clicked in the BLACS camera tab.
These are just remnants due to the fact that the PCOCamera module inherits a lot of code from the IMAQdx module.
The PCOCamera module doesn't use IMAQdx or any National Instruments software.
* PCO Cameras that connect via FireWire may need additional space in their buffers.
If you use a PCO camera with a FireWire interface, let the authors know if it works or if you run into issues.
* PCO Cameras with internal memory may require some different configuration steps to make use of it.
Again, if you have such a camera, give it a try and let the authors know how it goes.
* The Linux version of the PCO SDK has not yet been tested and likely will not work with the current version of this module.
