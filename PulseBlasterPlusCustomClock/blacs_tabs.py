from labscript_devices.PulseBlaster_No_DDS import Pulseblaster_No_DDS_Tab
from userlib.user_devices.RbLab.PulseBlasterPlusCustomClock.blacs_workers import PulseBlasterPlusCustomClockWorker


class PulseBlasterPlusCustomClockTab(Pulseblaster_No_DDS_Tab):
    # Capabilities
    num_DO = 24

    def __init__(self, *args, **kwargs):
        self.device_worker_class = PulseBlasterPlusCustomClockWorker
        Pulseblaster_No_DDS_Tab.__init__(self, *args, **kwargs)
