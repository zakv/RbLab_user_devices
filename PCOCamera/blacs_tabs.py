from labscript_devices.IMAQdxCamera.blacs_tabs import IMAQdxCameraTab


class PCOCameraTab(IMAQdxCameraTab):

    # Override worker class.
    worker_class = 'userlib.user_devices.RbLab.PCOCamera.blacs_workers.PCOCameraWorker'
