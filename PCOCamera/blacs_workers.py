# TODO: Copyright info
"""A module for interfacing PCO Cameras with Labscript.

This module uses PCO's Software Development Kit (SDK) to interace with a PCO
camera. Some initial setup, including installing dependencies is required before
this module can be used. See the README.md in this folder for more details.

Typical usage is to add something like the cod below to your connectiontable.py.
You will likely want to keep the camera_attributes and
manual_mode_camera_attributes arguments commented out until you get a list of
supported camera attributes from BLACS:
```
from labscript_devices.PCOCamera.labscript_devices import PCOCamera
camera = PCOCamera(
    "camera",
    parent_device=ni_pci_dio_32hs_dev3,
    connection='port1/line0',
    serial_number=269,
    orientation=None,
    trigger_edge_type='rising',
    trigger_duration=5e-3,
    minimum_recovery_time=0.0,
    # camera_attributes={
    #     'SensorFormat': 0,
    #     'Binning': (1, 1),
    #     'PixelRate': 24000000,
    #     'IRSensitivity': 1,
    #     'DelayExposureTime': (0, 5, 0, 2),
    #     'TriggerMode': 2,
    #     'TimestampMode': 0,
    #     'ROI': {'offsetX': 546, 'offsetY': 470, 'width': 300, 'height': 170},
    #     'fliplr': False,
    #     'flipud': False,
    # },
    # manual_mode_camera_attributes={
    #     'SensorFormat': 0,
    #     'Binning': (1, 1),
    #     'PixelRate': 24000000,
    #     'IRSensitivity': 1,
    #     'DelayExposureTime': (0, 5, 0, 2),
    #     'TriggerMode': 0,
    #     'TimestampMode': 0,
    #     'ROI': {'offsetX': 0, 'offsetY': 0, 'width': 1392, 'height': 1040},
    #     'fliplr': False,
    #     'flipud': False,
    # },
    stop_acquisition_timeout=5.0,
    exception_on_failed_shot=True,
    saved_attribute_visibility_level='advanced',
    mock=False)
    ```

Once the camera has been added to connectiontable.py, it can be used in a
sequence by calling its expose() method e.g.:
```
camera.expose(t, 'name', frametype='frame')
```
where 'name' should be replaced by a string describing the kind of imaging being
done (e.g. 'absorption') and frametype can optionally be set to the type of
image that this particular exposure corresponds to, e.g. 'atoms', 'probe', or
'background' for absorption imaging.
"""
from math import ceil
import numpy as np

from labscript_devices.IMAQdxCamera.blacs_workers import IMAQdxCameraWorker

# Don't import specific dependencies yet so as not to throw an error,
# allow worker to run as a dummy device, or for subclasses to import this
# module to inherit classes without requiring these dependencies
instrumental = None
ffi = None
NicePCO = None
PCOError = None


class PCOCamera(object):
    """A high-level interface for working with PCO cameras.

    Mid-level interfacing to the PCO SDK's library S2C_Cam.dll is performed via
    the python packages Instrumental, NiceLib, and CFFI as well as some
    additional code included in pco_sdk_wrappers.py in this directory. This code
    is not designed to be used directly, but rather called by labscript. For
    that reason the distinction between public and private methods and
    properties is done somewhat haphazardly.

    Attributes:
        attribute_names: A list of strings, each of which is the name of a
            camera attribute that can be set in connectiontable.py. Thus far,
            the 'visibility_level' property used for IMAQdx cameras is not used
            or implemented here.
        camera_description: The struct returned by PCO_GetCameraDescription().
            See the PCO SDK manual for a list of this struct's properties. Those
            properties can be accessed in an object-oriented way by calling e.g.
            camera.camera_description.wMaxBinHorzDESC. Note that this can be
            used to access info about the camera, but can NOT be used to change
            camera settings.
        bit_depth: The number of bits of resolution of the camera.
    """
    # Set constants
    _PCO_MAX_BUFFER_COUNT = 16

    def __init__(self, serial_number):
        """Connect to and initialize a pco camera.

        Args:
            serial_number (int): The serial number of the desired camera
        """
        # Import dependencies that shouldn't be imported unless a PCO camera is
        # in use.
        global instrumental
        import instrumental
        import userlib.user_devices.RbLab.PCOCamera.pco_sdk_wrappers as pco_sdk_wrappers
        global ffi
        ffi = pco_sdk_wrappers.ffi
        global NicePCO
        NicePCO = pco_sdk_wrappers.NicePCO
        global PCOError
        PCOError = pco_sdk_wrappers.PCOError

        # Connect to camera
        self._open_camera(serial_number)

        # Make sure the camera always starts in the same clean default state
        self.reinitialize_camera()

        # Initialize state-tracking properties
        self._abort_acquisition = False
        self._using_hardware_trigger = True
        self._running_continuously = False

        # Set some instance properties
        self.camera_description = self.camera.GetCameraDescription()
        self.bit_depth = self.camera_description.wDynResDESC
        self.grab_timeout_ms = 1e3

        # Make list of changeable attributes
        self.attribute_names = [
            "SensorFormat",
            "Binning",
            "PixelRate",
            "IRSensitivity",
            "DelayExposureTime",
            "TriggerMode",
            "TimestampMode",
            "ROI",  # ROI will be hand-implemented in code here
            "fliplr",
            "flipud",
        ]
        # Default ROI will be full image
        ROI = {
            'offsetX': 0,
            'offsetY': 0,
            'width': self.camera_description.wMaxHorzResStdDESC,
            'height': self.camera_description.wMaxVertResStdDESC,
        }
        self.set_ROI(ROI)
        # Don't flip image at all by default
        fliplr = False
        flipud = False
        self.set_fliplr(fliplr)
        self.set_flipud(flipud)

    def _open_camera(self, target_serial_number):
        """Open the desired PCO camera and set it as self.camera.

        This function keeps opening attached PCO cameras until the desired
        camera is found, identified by its serial number.

        Args:
            target_serial_number (int): The serial number of the desired camera.
        """
        # Repeatedly open cameras with OpenCamera()
        camera_list = []
        serial_number_list = []
        looking_for_camera = True
        while looking_for_camera:
            try:
                camera_handle = NicePCO.OpenCamera()
            except PCOError as err:
                # See if error code corresponds to not finding any more cameras
                if err.return_code == PCOError.hex_string_to_return_code(
                        "0x800a300d"):
                    # Ran out of cameras to check
                    looking_for_camera = False
                    found_camera = False
                else:
                    # In this case we got some weird error, let's re-raise it
                    raise err
            if looking_for_camera:
                # Only get serial number if camera successfully opened
                camera = NicePCO.Camera(camera_handle)
                camera_list.append(camera)
                serial_number = camera.GetCameraType().dwSerialNumber
                serial_number_list.append(serial_number)
                if serial_number == target_serial_number:
                    looking_for_camera = False
                    found_camera = True

        if found_camera:
            self.camera = camera_list.pop(-1)

        # Close undesired cameras
        for camera in camera_list:
            camera.CloseCamera()

        if not found_camera:
            error_text = (f"Could not find PCO Camera with serial number "
                          f"{target_serial_number}, found serial numbers: "
                          f"{serial_number_list}")
            raise ConnectionAbortedError(error_text)

    def reinitialize_camera(self):
        """Return camera to a clean and consistent starting state.

        This function stops the camera from recording, returns the camera
        settings to their default values, and frees any buffers. The default
        values are those set by the PCO SDK function
        PCO_RResetSettingsToDefault(), except that the bit alignment is set to
        1 (least significant bit) with PCO_SetBitAlignment.
        """
        # Make sure it is not recording before changing anything to avoid
        # errors
        self.stop_acquisition()
        self.clean_up_buffers()
        self.camera.ResetSettingsToDefault()
        self.camera.SetBitAlignment(1)

    def clean_up_buffers(self):
        """Remove buffers from queue and free their memory."""
        # Remove all buffers from image queue
        self.camera.CancelImages()

        # Free buffers if they exist
        for n in range(self._PCO_MAX_BUFFER_COUNT):
            try:
                self.camera.FreeBuffer(n)
            except PCOError:
                pass

        self.buffer_info_list = []

    def set_attributes(self, attr_dict):
        """Set many camera settings at once.

        This function repeatedly calls self.set_attribute(), once for each key-
        value pair in attr_dict.

        Args:
            attr_dict (dict): A dictionary which has keys that are strings, each
                specifying a camera attribute (e.g. 'IRSensitivity'). The values
                corresponding to those keys should be the desired values for
                those settings. To get a list of possible settings, add a PCO
                camera to connectiontable.py, then click on the "Attributes"
                button in BLACS.
        """
        for prop, val in attr_dict.items():
            self.set_attribute(prop, val)

    def set_attribute(self, name, value):
        """Set the camera attribute name to be value.

        Args:
            name (str): A string specifying which property to set. This should
                be one of the attributes listed in BLACS when "Attributes" is
                clicked in the device tab.
            value: The desired value of the property.
        """
        if name == 'ROI':
            self.set_ROI(value)
        elif name == 'fliplr':
            self.set_fliplr(value)
        elif name == 'flipud':
            self.set_flipud(value)
        else:
            set_function = getattr(self.camera, 'Set' + name)
            try:
                # Unpack tuples/lists into multiple arguments. Throws TypeError
                # if value isn't an interable.
                set_function(*value)
            except TypeError:
                # In this case value isn't an iterable so we won't unpack it
                set_function(value)

    def set_ROI(self, ROI):
        """Set the software Region Of Interest.

        Not all PCO Cameras support hardware ROI, so thus far ROI has only been
        implemented at the software level.

        Args:
            ROI (dict): A dictionary which has the following keys: 'offsetX',
                'offsetY', 'width', and 'height'. The value corresponding to
                each of those should be a nonnegative integer.

        Raises:
            ValueError: If the values for any of those properties aren't
                nonnegative integers or the ROI extends out of the bounds of the
                image.
        """
        # Ensure ROI has requisite keys
        required_keys = set(('offsetX', 'offsetY', 'width', 'height'))
        if not required_keys.issubset(ROI):
            # In this case not all required keys are present
            error_text = ("Camera attribute ROI must be a dict with the"
                          f"following keys: {required_keys}")
            raise ValueError(error_text)

        # Ensure all quantities are nonnegative
        for key in required_keys:
            self._check_ROI_dict_value_is_nonnegative(ROI, key)

        # Ensure ROI fits in image
        # Call ArmCamera() to make sure any changes to binning etc. are applied
        # before the camera calculates its image size
        self.camera.ArmCamera()
        image_width_pixels, image_height_pixels = self.get_image_width_and_height()
        x_index_max = ROI['offsetX'] + ROI['width']
        y_index_max = ROI['offsetY'] + ROI['height']

        if x_index_max > image_width_pixels:
            error_text = ("ROI's offsetX + width must be less than the image "
                          f"width ({image_width_pixels}) but is {x_index_max}")
            raise ValueError(error_text)
        if y_index_max > image_height_pixels:
            error_text = ("ROI's offsetY + height must be less than the image "
                          f"height ({image_height_pixels}) but is {y_index_max}")
            raise ValueError(error_text)

        # If code hasn't errored out by now, it's safe to set the ROI
        self.ROI = ROI

    def _check_ROI_dict_value_is_nonnegative(self, ROI, key):
        """Make sure that the value of ROI[key] is a nonnegative integer.

        Args:
            ROI (dict): A dict of the format required by set_ROI()
            key (str): A string which should be one of the keys in ROI

        Raises:
            ValueError: If ROI[key] isn't a nonnegative integer, a ValueError is
                raised.
        """
        value = ROI[key]
        if type(value) is not int or value < 0:
            error_text = (f"Camera attribute ROI's {key} must be a "
                          f"nonnegative integer but is {value}")
            raise ValueError(error_text)

    def set_fliplr(self, fliplr):
        """Sets whether or not the acquired image is flipped left-to-right.

        Args:
            fliplr (bool): Whether or not the image should be flipped
                left-to-right after being retrieved from the camera.

        Raises:
            ValueError: If fliplr isn't a boolean, a ValueError is raised.
        """
        if type(fliplr) is not bool:
            error_text = ("Camera attribute fliplr must be a boolean but "
                          f"was set to {fliplr}")
            raise ValueError(error_text)
        self.fliplr = fliplr

    def set_flipud(self, flipud):
        """Sets whether or not the acquired image is flipped up-to-down.

        Args:
            flipud (bool): Whether or not the image should be flipped
                up-to-down after being retrieved from the camera.

        Raises:
            ValueError: If flipud isn't a boolean, a ValueError is raised.
        """
        if type(flipud) is not bool:
            error_text = ("Camera attribute flipud must be a boolean but "
                          f"was set to {flipud}")
            raise ValueError(error_text)
        self.flipud = flipud

    def get_attribute_names(self, visibility_level, writeable_only=True):
        """Return a list of names of camera attributes.

        There isn't a built-in function for this in the PCO SDK, so this simply

        Args:
            visibility_level (str): NOT Implemented. Nominally should be one of
                the following strings: 'simple', 'intermediate', or 'advanced'.
                However, this feature is not implemented. It is only retained
                here to maintain compatibility with code inherited from the
                IMAQdx camera module.
            writeable_only (bool): (Default value = True) NOT Implemented.
                Nominally if set to True, only the names of attributes which can
                be changed would be returned, but this is NOT yet implemented.

        Returns:
            attribute_names: A list of strings, each of which is a camera
                attribute.
        """
        return self.attribute_names

    def get_attribute(self, name):
        """Get the value of a specific camera attribute.

        Args:
            name (str): The name of the desired camera attribute.

        Returns:
            value: The value of the desired camera attribute.
        """
        if name == 'ROI':
            return self.ROI
        elif name == 'fliplr':
            return self.fliplr
        elif name == 'flipud':
            return self.flipud
        else:
            get_function = getattr(self.camera, 'Get' + name)
            value = get_function()
        return value

    def snap(self):
        """Acquire a single image and return it."""
        self.configure_acquisition(continuous=False, bufferCount=1, snap=True)
        image = self.grab()
        self.stop_acquisition()
        return image

    def configure_acquisition(self, continuous=True,
                              bufferCount=2, snap=False):
        """Prepare camera for image acquisition.

        This function assumes that the camera attributes have already been set
        to their desired values. It simply sets up the buffers and sets the
        camera to start recording.

        Args:
            continuous (bool):  (Default value = True) Set to true if doing live
                video for which images should be acquired continuously.
            bufferCount (int):  (Default value = 2) The number of buffers to
                prepare to hold images as they are acquired.
            snap (bool):  (Default value = False) Set to true if acquiring a single
                image. This is used when the snap button is pressed in BLACS.
        """
        self._running_continuously = continuous
        if continuous or snap:
            self._using_hardware_trigger = False
        else:
            self._using_hardware_trigger = True

        # Recording must be stopped before configuring the settings below
        self.stop_acquisition()
        self.clean_up_buffers()

        # Set storage mode
        # Set to 0 for recorder mode or 1 for FIFO mode
        storage_mode_selection = 1
        self.camera.SetStorageMode(storage_mode_selection)

        # Set recorder submode
        # Set to 0 for sequence or 1 for ring buffer.
        # Only has an effect is storage mode is "recorder". Doesn't have any
        # effect if storage mode is FIFO
        recorder_submode_selection = 1
        self.camera.SetRecorderSubmode(recorder_submode_selection)

        # Arm Camera to apply settings
        self.camera.ArmCamera()

        # Set recording state to 0 for "stop" or 1 for "run"
        # Had to be done before buffer allocation in tests
        self.camera.SetRecordingState(1)

        # Allocate and queue up buffers
        buffer_size_bytes = self.get_buffer_size_bytes()
        for _ in range(bufferCount):
            # Create the actual buffer
            buffer_index, buffer_pointer, event_handle = self.camera.AllocateBuffer(
                -1, buffer_size_bytes, ffi.NULL, ffi.NULL)
            # Use a BufferInfo instance to store the actual buffer's info
            new_buffer = instrumental.drivers.cameras.pco.BufferInfo(
                buffer_index, buffer_pointer, event_handle)
            self.queue_buffer(new_buffer)

    def get_image_width_and_height(self):
        """Get the dimensions of the image that will be returned by the camera.

        Note that the values returned by this function depend on camera settings
        (such as binning). This function always returns the most up-to-date
        values for the image width and height based on the camera settings at
        the time of the most recent call to self.camera.ArmCamera().

        Returns:
            (image_width_pixels, image_height_pixels): The width and height of
                the image, measured in pixels.
        """
        image_width_pixels, image_height_pixels, _, _ = self.camera.GetSizes()
        return (image_width_pixels, image_height_pixels)

    def get_buffer_size_bytes(self):
        """Return the required size in bytes of a buffer.

        The size will depend on the image's width and height (in pixels) and the
        bit depth of the camera. This function calls
        self.get_image_width_and_height(), so its note about
        self.camera.ArmCamera() is also applicable here.

        Note that a PCO camera with a firewire interface may require extra space
        in the buffer. At the moment this is not supported and is NOT
        implemented here. If you have issues using a firewire camera, contact
        the authors of this code.

        Returns:
            buffer_size_bytes (int): The size of buffer in bytes necessary to
                hold an image from the camera.
        """
        image_width_pixels, image_height_pixels = self.get_image_width_and_height()
        bytes_per_pixel = ceil(self.bit_depth / 8.)
        buffer_size_bytes = image_width_pixels * image_height_pixels * bytes_per_pixel
        return buffer_size_bytes

    def queue_buffer(self, buffer_info):
        """Add a buffer to the queue to receive images from the camera.

        Args:
            buffer_info: An instance of the BufferInfo class from
                instrumental.drivers.cameras.pco which holds the information of
                the buffer which should be queued to receive data from the
                camera.
        """
        image_width_pixels, image_height_pixels = self.get_image_width_and_height()
        buffer_index = buffer_info.num
        self.camera.AddBufferEx(
            0,
            0,
            buffer_index,
            image_width_pixels,
            image_height_pixels,
            self.bit_depth)
        self.buffer_info_list.append(buffer_info)

    def wait_for_buffer(self, buffer_info, timeout_ms):
        """Wait until the buffer has been filled with an image.

        Args:
            buffer_info: An instance of the BufferInfo class from
                instrumental.drivers.cameras.pco which holds the information of
                the buffer.
            timeout_ms (int):  time (in milliseconds) to wait before raising a
                timeout error.

        Raises:
            PCOError: If a timeout occurs, a PCOError with code "0xA00A3005"
                be raise. A PCOError with a different error code is also
                possible if PCO_WaitforBuffer() has any other issues.
        """
        buffer_number = buffer_info.num
        pco_buflist = ffi.new('PCO_Buflist *')
        pco_buflist.sBufNr = buffer_number

        # Wait for buffer to get filled, will error if timeout occurs
        self.camera.WaitforBuffer(1, pco_buflist, timeout_ms)

    def grab(self):
        """Grab and return a single image during pre-configured acquisition."""
        # Get an image from first buffer in queue. Wait for buffer to be filled
        # (if not already filled), will error on timeout.
        buffer_info = self.buffer_info_list[0]
        timeout_ms = self.grab_timeout_ms
        self.wait_for_buffer(buffer_info, timeout_ms)

        # Now remove buffer_info from buffer_info_list. That way it isn't
        # removed if the above times out.
        self.buffer_info_list.pop(0)

        image = self._get_image_from_buffer(buffer_info)

        # Put buffer back into end of queue if acquiring continuously
        if self._running_continuously:
            self.queue_buffer(buffer_info)

        return image

    def grab_multiple(self, n_images, images):
        """Grab n_images into images array during buffered acquisition.

        The acquired images are not returned. Instead they are appended to the
        images input.

        Args:
            n_images (int): The number of images to acquire.
            images (list): A list to which the newly acquired images will be
            appended.
        """
        last_buffer_info = self.buffer_info_list[-1]
        # Set time (milliseconds) between checking for abort signal
        abort_check_period = 1e3

        print(f"Attempting to grab {n_images} images.", end='')
        while True:
            if self._abort_acquisition:
                print("Abort during acquisition.")
                self._abort_acquisition = False
                return
            try:
                # Wait until all buffers are filled
                self.wait_for_buffer(last_buffer_info, abort_check_period)
                for _ in range(n_images):
                    image = self.grab()
                    images.append(image)
                break
            except PCOError as err:
                # Only catch timeout errors (return code 0xA00A3005)
                timeout_code = PCOError.hex_string_to_return_code("0xA00A3005")
                if err.return_code == timeout_code:
                    print('.', end='')
                    continue
                else:
                    raise err
        print(f"\nGot {len(images)} of {n_images} images.")

    def _get_image_from_buffer(self, buffer_info):
        """Get data from buffer into a numpy array.

        This function applies the ROI setting and the fliplr/flipud settings as
        the data is transferred from the buffer. It is also worth noting that
        the data is copied, so the buffer can be used again without overwriting
        the data.

        Args:
            buffer_info: An instance of the BufferInfo class from
                instrumental.drivers.cameras.pco which holds the information of
                the buffer.

        Returns:
            array (numpy array): A 2D array holding the image from the buffer.
        """
        # Gather up necessary image/buffer info
        image_width_pixels, image_height_pixels = self.get_image_width_and_height()
        buffer_size_bytes = self.get_buffer_size_bytes()
        buffer_pointer = buffer_info.address

        # Copy the data out of the buffer into a numpy array
        ffi_buffer = ffi.buffer(buffer_pointer, buffer_size_bytes)
        buffer_data = memoryview(ffi_buffer)
        array = np.frombuffer(buffer_data, np.uint16)
        array = array.reshape((image_height_pixels, image_width_pixels))

        # Implement ROI
        x_index_min = self.ROI['offsetX']
        x_index_max = self.ROI['offsetX'] + self.ROI['width']
        y_index_min = self.ROI['offsetY']
        y_index_max = self.ROI['offsetY'] + self.ROI['height']
        array = array[y_index_min:y_index_max, x_index_min:x_index_max]

        # Reverse array directions if configured to do so
        if self.fliplr:
            array = np.fliplr(array)
        if self.flipud:
            array = np.flipud(array)

        # Copy data out of buffer, which also makes it contiguous for BLACS
        array = array.copy()

        return array

    def stop_acquisition(self):
        """Stops the acquisition if the camera is running.

        This function does NOT clean up buffers or reset camera settings
        """
        # Only stop recording if currently recording to avoid error
        if self.camera.GetRecordingState():
            self.camera.SetRecordingState(0)

    def abort_acquisition(self):
        """Call this function to abort a buffered image acquisition."""
        self._abort_acquisition = True

    def close(self):
        """Disconnect from the camera."""
        self.camera.CloseCamera()


class PCOCameraWorker(IMAQdxCameraWorker):
    """PCO API Camera Worker.

    Inherits from IMAQdxCameraWorker.

    Args:
        See base class.
    """
    interface_class = PCOCamera
