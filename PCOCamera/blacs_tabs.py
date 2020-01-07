from labscript_devices.IMAQdxCamera.blacs_tabs import IMAQdxCameraTab


class PCOCameraTab(IMAQdxCameraTab):

    # override worker class
    # worker_class = 'labscript_devices.PCOCamera.blacs_workers.PCOCameraWorker'
    worker_class = 'userlib.labscriptlib.RbLab.PCOCamera.blacs_workers.PCOCameraWorker'
