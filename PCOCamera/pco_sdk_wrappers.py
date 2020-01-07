import os

from nicelib import NiceLib, NiceObject, Sig, RetHandler

# Add some helpful error text if instrumental can't find the camera driver
# library
try:
    import instrumental.drivers.cameras.pco
except OSError as err:
    original_error_text = err.args[0]
    additional_error_text = (". Make sure path to 'SC2_Cam.dll' is in PATH "
                             "environment variable. See README.md in PCOCamera "
                             "folder for more details.")
    error_text = original_error_text + additional_error_text
    raise OSError(error_text) from None


# Use the ffi instance and lib instance from instrumental, which have
# store the header data and compiled libraries from the PCO SDK.
ffi = instrumental.drivers.cameras.pco.ffi
lib = instrumental.drivers.cameras.pco.lib


class PCOError(Exception):
    def __init__(self, return_code):
        error_text = self.get_error_text(return_code)

        # Call the base class constructor with the parameters it needs
        super().__init__(error_text)

        self.return_code = return_code

    @staticmethod
    def return_code_to_hex_string(return_code):
        """Write the return code integer as a hex string

        This is the inverse of PCOError.return_code_to_hex_string()
        """
        return_code_bytes = return_code.to_bytes(
            4, byteorder="big", signed=True)
        return_code_hex_string = return_code_bytes.hex().upper()
        return_code_hex_string = "0x" + return_code_hex_string
        return return_code_hex_string

    @staticmethod
    def hex_string_to_return_code(hex_string):
        """Convert a hex string into the corresponding return code integer

        This is the inverse of PCOError.return_code_to_hex_string(). The string
        provided should only contain the characters 0-9 and A-F.

        Example: PCOError.hex_string_to_return_code("0xF00000FF")
        """
        # Strip leading "0x" if present
        if hex_string[0:2] == "0x":
            hex_string = hex_string[2:]

        return_code_bytes = bytes.fromhex(hex_string)
        return_code = int.from_bytes(
            return_code_bytes, byteorder="big", signed=True)

        return return_code

    @classmethod
    def get_error_text(cls, return_code):
        """Turn a pco.sdk error code into a useful/informative string

        Use instrumental's equivalent function if possible. Only works if some C
        code is compiled, which may be done automatically during installation,
        or may need to be done manually. Otherwise it will raise a
        ModuleNotFoundError. See issue 30 on instrumental's github:
        https://github.com/mabuchilab/Instrumental/issues/30

        If instrumental's function doesn't work, this function will convert the
        error code to a hex string and refer the user to the PCO_errt.h from the
        PCO SDK to interpret the error manually. Additional info about the
        formatting of error codes is available in PCO_err.h (note the missing
        "t" in this file name compared to the other one).
        """
        try:
            # Use instrumental's nice wrapper of PCO_GetErrorText()
            return instrumental.drivers.cameras.pco.get_error_text(return_code)
        except ImportError:
            # If the wrapper doesn't work, we'll just print out the error code
            # as a hex string
            return_code_hex = cls.return_code_to_hex_string(return_code)
            if return_code_hex[0:3] == "0xA":
                # "Common errors" start with 0xA and have more bits masked in
                # PCO_errt.h. In this case we need to mask all but first 4
                # bits and last 8 bits.
                mask = cls.hex_string_to_return_code("0xF00000FF")
            else:
                # For other errors fewer bits are masked
                mask = cls.hex_string_to_return_code("0xF000FFFF")

            # This masked code should appear in PCO_errt.h in a comment next to
            # the error string
            masked_return_code = return_code & mask
            masked_return_code_hex = cls.return_code_to_hex_string(
                masked_return_code)

            error_text = f"PCO Error code: {return_code_hex}, "
            error_text += f"Look for {masked_return_code_hex} in PCO_errt.h"

            return error_text

# Replace instrumental.drivers.cameras.pco's pco_errcheck() to use
# PCOError defined here
@RetHandler(num_retvals=0)
def pco_error_check(return_code):
    if return_code != 0:
        error = PCOError(return_code)
        raise error


# Make custom NicePCO and Camera classes rather than using the ones in
# instrumental in order to fix bugs and add additional pco.sdk function
# wrappers.
class NicePCO(NiceLib):
    _ffi_ = ffi
    _ffilib_ = lib
    _prefix_ = 'PCO_'
    _ret_ = pco_error_check

    def _struct_maker_(*args):  # pylint: disable=no-method-argument
        """PCO makes you fill in the wSize field of many structs"""
        struct_p = ffi.new(*args)  # pylint: disable=no-value-for-parameter

        # Only set wSize if the object has that property
        if hasattr(struct_p[0], 'wSize'):
            struct_p[0].wSize = ffi.sizeof(struct_p[0])

        for name, field in ffi.typeof(struct_p[0]).fields:
            # Only goes one level deep for now
            if field.type.kind == 'struct':
                s = getattr(struct_p[0], name)
                # Only set wSize if the object has that property
                if hasattr(s, 'wSize'):
                    s.wSize = ffi.sizeof(s)
        return struct_p

    # Wrap functions that do not belong as camera methods
    OpenCamera = Sig('out', 'ignore')
    OpenCameraEx = Sig('out', 'inout')

    class Camera(NiceObject):
        # Note: Not all functions are wrapped yet. Additionally, not all PCO
        # cameras support all pco.sdk functions. Some functions may be manually
        # wrapped using cffi directly if NiceLib can't handle the function
        # directly, e.g. GetTransferParameter() below

        # Functions from pco.sdk manual section 2.1 "Camera Access"
        CloseCamera = Sig('in')

        # Functions from pco.sdk manual section 2.2 "Camera Description"
        GetCameraDescription = Sig('in', 'out')

        # Functions from pco.sdk manual section 2.3 "General Camera Status"
        GetCameraType = Sig('in', 'out')
        GetInfoString = Sig('in', 'in', 'buf', 'len')
        GetCameraName = Sig('in', 'buf', 'len', buflen=40)
        GetFirmwareInfo = Sig('in', 'in', 'out')

        # Functions from pco.sdk manual section 2.4 "General Camera Control"
        ArmCamera = Sig('in')
        CamLinkSetImageParameters = Sig('in', 'in', 'in')
        ResetSettingsToDefault = Sig('in')

        # Functions from pco.sdk manual section 2.5 "Image Sensor"
        GetSizes = Sig('in', 'out', 'out', 'out', 'out')
        GetSensorFormat = Sig('in', 'out')
        SetSensorFormat = Sig('in', 'in')
        GetROI = Sig('in', 'out', 'out', 'out', 'out')
        SetROI = Sig('in', 'in', 'in', 'in', 'in')
        GetBinning = Sig('in', 'out', 'out')
        SetBinning = Sig('in', 'in', 'in')
        GetPixelRate = Sig('in', 'out')
        SetPixelRate = Sig('in', 'in')
        GetIRSensitivity = Sig('in', 'out')
        SetIRSensitivity = Sig('in', 'in')
        GetActiveLookupTable = Sig('in', 'out', 'out')
        SetActiveLookupTable = Sig('in', 'inout', 'inout')
        GetLookupTableInfo = Sig('in', 'in', 'out', 'buf', 'len', 'out', 'out', 'out', 'out',
                                 buflen=20)

        # Functions from pco.sdk manual section 2.6 "Timing Control"
        GetDelayExposureTime = Sig('in', 'out', 'out', 'out', 'out')
        SetDelayExposureTime = Sig('in', 'in', 'in', 'in', 'in')
        GetFrameRate = Sig('in', 'out', 'out', 'out')
        SetFrameRate = Sig('in', 'out', 'in', 'inout', 'inout')
        GetTriggerMode = Sig('in', 'out')
        SetTriggerMode = Sig('in', 'in')
        ForceTrigger = Sig('in', 'out')
        GetHWIOSignalDescriptor = Sig('in', 'in', 'out')
        GetHWIOSignal = Sig('in', 'in', 'out')
        SetHWIOSignal = Sig('in', 'in', 'in')
        GetTimestampMode = Sig('in', 'out')
        SetTimestampMode = Sig('in', 'in')

        # Functions from pco.sdk manual section 2.7 "Recording Control"
        GetRecordingState = Sig('in', 'out')
        SetRecordingState = Sig('in', 'in')
        GetStorageMode = Sig('in', 'out')
        SetStorageMode = Sig('in', 'in')
        GetRecorderSubmode = Sig('in', 'out')
        SetRecorderSubmode = Sig('in', 'in')

        # Functions from pco.sdk manual section 2.8 "Storage Control"
        GetActiveRamSegment = Sig('in', 'out')

        # Functions from pco.sdk manual section 2.9 "Image Information"
        GetSegmentStruct = Sig('in', 'out', 'out')
        GetNumberOfImagesInSegment = Sig('in', 'in', 'out', 'out')
        GetBitAlignment = Sig('in', 'out')
        SetBitAlignment = Sig('in', 'in')

        # Functions from pco.sdk manual section 2.10 "Buffer Management"
        AllocateBuffer = Sig('in', 'inout', 'in', 'inout', 'inout')
        FreeBuffer = Sig('in', 'in')
        GetBufferStatus = Sig('in', 'in', 'out', 'out')
        GetBuffer = Sig('in', 'in', 'out', 'out')

        # Functions from pco.sdk manual section 2.11 "Image Acquisition"
        GetImageEx = Sig('in', 'in', 'in', 'in', 'in', 'in', 'in', 'in')
        AddBufferEx = Sig('in', 'in', 'in', 'in', 'in', 'in', 'in')
        CancelImages = Sig('in')
        GetPendingBuffer = Sig('in', 'out')
        WaitforBuffer = Sig('in', 'in', 'in', 'in')
        EnableSoftROI = Sig('in', 'in', 'in', 'in')

        # Functions from pco.sdk manual section 2.12 "Driver Management"
        def GetTransferParameter(self):
            # This function needs to be wrapped manually because the buffer
            # object passed to it is a void * and the type of the structure
            # that it points to depends on the camera's interface type (USB,
            # Firewire, etc.)
            camera_handle, = self._handles

            # Figure out type of interface, necessary to make correct type for
            # params_p. See PCO documentation on Transfer Parameter Structures
            # and PCO_GetCameraType's Interface Type Codes.
            interface_type_index = self.GetCameraType().wInterfaceType
            interface_params_dict = {
                1: 'PCO_1394_TRANSFER_PARAM',  # Firewire
                2: 'PCO_SC2_CL_TRANSFER_PARAM',  # Camera Link
                3: 'PCO_USB_TRANSFER_PARAM',  # USB 2.0
                4: 'PCO_GIGE_TRANSFER_PARAM',  # GigE
                5: '',  # Serial Interface, Not sure what to put here
                6: 'PCO_USB_TRANSFER_PARAM',  # USB 3.0
                7: 'PCO_SC2_CL_TRANSFER_PARAM',  # CLHS
            }

            # Construct input arguments
            struct_type = interface_params_dict[interface_type_index]
            params_p = ffi.new(struct_type + ' *')
            void_p = ffi.cast('void *', params_p)
            struct_size = ffi.sizeof(params_p[0])

            # Finally call the library function and return the result
            return_code = lib.PCO_GetTransferParameter(
                camera_handle, void_p, struct_size)
            pco_error_check.__func__(return_code)  # pylint: disable=no-member
            return params_p[0]

        # Functions from pco.sdk manual section 2.13 "Special Commands
        # PCO.Edge"
        SetTransferParametersAuto = Sig('in', 'ignore', 'ignore')

        # Functions from pco.sdk manual section 2.14 "Special Commands
        # PCO.Dimax"

        # Functions from pco.sdk manual section 2.15 "Special Commands
        # PCO.Dimax with HD-SDI"

        # Functions from pco.sdk manual section 2.16 "Special Commands
        # PCO.Film"

        # Functions from pco.sdk manual section 2.17 "Lens Control"

        # Functions from pco.sdk manual section 2.18 "Special Commands
        # PCO.Dicam"
