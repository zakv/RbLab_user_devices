from labscript_devices import register_classes

register_classes(
    'PCOCamera',
    BLACS_tab='userlib.user_devices.RbLab.PCOCamera.blacs_tabs.PCOCameraTab',
    runviewer_parser=None,
)
