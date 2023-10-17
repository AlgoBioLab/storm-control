import numpy as np
from typing import Tuple
import os
import sys

from storm_control.hal4000.qpdEmulation.cameraInterface import Camera
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK


def dll_path_config(dll_folder_location: str):
    """
    Adds the locations of the Native DLLs to the PATH.
    Expects to be provided a folder with the following two sub folder
    
    * 64_lib
    * 32_lib

    This code is based on the ThorLabs provided `windows_setup` script
    """
    is_64bits = sys.maxsize > 2**32

    # Determine if the path should point to the 64 bit dlls or 32 bit dlls
    path_to_dlls = dll_folder_location + os.sep
    if is_64bits:
        path_to_dlls += '64_lib'
    else:
        path_to_dlls += '32_lib'

    os.environ['PATH'] = path_to_dlls + os.pathsep + os.environ['PATH']

    try:
        # Python 3.8 introduces a new method to specify dll directory
        os.add_dll_directory(path_to_dlls)
    except AttributeError:
        pass


class ScientificCamera(Camera):
    def __init__(self, module_params = None, qt_settings=None, **kwds):
        super().__init__(**kwds)

        configuration = module_params.get('configuration')
        self.dll_path = configuration.get('ddl_path')
        self.camera_id = configuration.get('camera_id')
        self.exposure_time = configuration.get('exposure_time_us')
        self.timeout = configuration.get('timeout_ms')

        # Add DLLs
        dll_path_config(self.dll_path)

        # Setup the SDK
        self.sdk = TLCameraSDK()

        # Select the correct camera (if multiple exist)
        available_cameras = self.sdk.discover_available_cameras()
        assert len(available_cameras) < self.camera_id, 'camera_id must be a valid index'
        self.camera = self.sdk.open_camera(available_cameras[self.camera_id])

        # Load camera settings
        self.camera.exposure_time_us = self.exposure_time
        self.camera.frames_per_trigger_zero_for_unlimited = 0
        self.camera.image_poll_timeout_ms = self.timeout

        # TODO: Handle dynamic change of AOI
        self.camera.roi = (700, 828, 875, 903)

        self.camera.arm(2)
        self.camera.issue_software_trigger()


    def getImage(self) -> np.ndarray:
        if not self.sdk._is_sdk_open:
            return None
        frame = self.camera.get_pending_frame_or_null()
        if frame is None:
            # TODO: More cleanly handle failed frame grabs
            raise 'Failed to get a frame'
        image = np.copy(frame.image_buffer)

        # Bound the image values from 0-255
        return ((image - image.min()) * (1/(image.max() - image.min()) * 255)).astype('uint8')

    def getTimeout(self) -> float:
        return 0.0
    
    def setTimeout(self, timeout: float) -> None:
        pass

    def getAOI(self) -> Tuple[int, int, int, int]:
        pass

    def setAOI(self, x_start: int, y_start: int, width: int, height: int) -> None:
        pass

    def shutdown(self) -> None:
        pass



        