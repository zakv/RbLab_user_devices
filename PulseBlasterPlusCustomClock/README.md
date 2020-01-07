# PulseBlasterPlusCustomClock README

## Introduction

RbLab has a "PulseBlaster Plus!", which is outdated and labscript technically
doesn't come with a class for it.
Additionally, For some reason our pulseblaster has a 180 MHz master clock oscillator inside of it instead of the standard 100 MHz that the documentation says it usually has.
To get around this, I (Zak) used PulsePlasterUSB.py to make PulseBlasterPlusCustomClock.py, which is the mostly the same.
The main difference is that the clock frequency and class names have been set to appropriate for values for our device.
Additionally, the code was restructured to use the "new register_classes() format" for registering devices with Labscript.
This allows us to store the code in the user_devices section of our git repo (if it were still set up with the old decorator-style method, the code would have to be stored in the labscript_devices directory outside of our git repo).
So far our PulseBlaster Plus has worked fine without any further changes to that code.
