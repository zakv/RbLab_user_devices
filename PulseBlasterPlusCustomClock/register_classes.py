from labscript_devices import register_classes

register_classes(
    'PulseBlasterPlusCustomClock',
    BLACS_tab='userlib.user_devices.RbLab.PulseBlasterPlusCustomClock.blacs_tabs.PulseBlasterPlusCustomClockTab',
    runviewer_parser='userlib.user_devices.RbLab.PulseBlasterPlusCustomClock.runviewer_parsers.PulseBlasterPlusCustomClockParser',
)
