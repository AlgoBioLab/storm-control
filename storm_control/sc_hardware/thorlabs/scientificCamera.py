import numpy as np
from typing import Tuple
import os
import sys
import cv2

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
        self.dll_path = configuration.get('dll_path')
        self.camera_id = configuration.get('camera_id')
        self.exposure_time = configuration.get('exposure_time_us')
        self.timeout = configuration.get('timeout_ms')

        # Add DLLs
        dll_path_config(self.dll_path)

        # Setup the SDK
        self.sdk = TLCameraSDK()

        # Select the correct camera (if multiple exist)
        available_cameras = self.sdk.discover_available_cameras()
        assert len(available_cameras) > self.camera_id, 'camera_id must be a valid index'
        self.camera = self.sdk.open_camera(available_cameras[self.camera_id])

        # Load camera settings
        self.camera.exposure_time_us = self.exposure_time
        self.camera.frames_per_trigger_zero_for_unlimited = 0
        self.camera.image_poll_timeout_ms = self.timeout

        self.camera.roi = (310, 560, 514, 764)
        self.max_height = self.camera.image_height_pixels
        self.max_width = self.camera.image_width_pixels

        self.camera.arm(2)
        self.camera.issue_software_trigger()

        # This count is to handle how many empty frames can be sent.
        # Empty frames are generated when a frame is not retrieved
        # by the camera
        self.max_empty_frames = 5
        self.num_empty_frames = 0

        # Keep a frame history a background image for use in the processing
        self.bg_image = cv2.imread("C:/Users/RPI/Desktop/background.jpg")
        self.bg_image = cv2.cvtColor(self.bg_image, cv2.COLOR_BGR2GRAY)
        print(self.bg_image.shape)

    def getImage(self) -> np.ndarray:
        if not self.sdk._is_sdk_open:
            return None

        frame = self.camera.get_pending_frame_or_null()
        if frame is None:
            if self.num_empty_frames >= self.max_empty_frames:
                # TODO: More cleanly handle failed frame grabs
                raise 'Failed to get a frame'
            else:
                # NOTE: Logic around allowing a number of empty frames is to
                # allow for the camera to re-arm after an AOI change
                self.num_empty_frames += 1
                return np.zeros((self.height, self.width))
        self.num_empty_frames = 0
        image = np.copy(frame.image_buffer).astype('uint8')
        ###
        # Parameters to tweak detection algorithm
        threshold_value = 40

        video_gray = image
        
        # Compute the absolute difference between the current frame and the background image
        fg_mask = cv2.absdiff(video_gray, self.bg_image)
        fg_mask = cv2.GaussianBlur(fg_mask, ksize=(5, 5), sigmaX=1)
        
        # Threshold the difference to create a binary mask
        _, fg_mask = cv2.threshold(fg_mask, threshold_value, 255, cv2.THRESH_BINARY)
        fg_mask = cv2.GaussianBlur(fg_mask, ksize=(11, 11), sigmaX=20)
        image = fg_mask

        return image

    def getTimeout(self) -> float:
        return 0.0
    
    def setTimeout(self, timeout: float) -> None:
        pass

    def getAOI(self) -> Tuple[int, int, int, int]:
        return [self.x_start, self.y_start, self.width, self.height]

    def setAOI(self, x_start: int, y_start: int, width: int, height: int) -> None:
        self.camera.disarm()
        self.x_start = x_start
        self.y_start = y_start
        self.width = width
        self.height = height
        self.camera.roi = (self.x_start, self.y_start, self.x_start + self.width, self.y_start + self.height)
        self.camera.arm(2)
        self.camera.issue_software_trigger()
    
    def get_max_height_width(self):
        return (self.max_height, self.max_width)

    def shutdown(self) -> None:
        pass



        