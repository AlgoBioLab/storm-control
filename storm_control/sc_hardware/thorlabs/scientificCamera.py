#!/usr/bin/env python
"""
Captured pictures for ThorLab Scientific Line of Cameras

Collin Bolles 9/23
"""
import ctypes.util
import ctypes.wintypes
import numpy
import os
import sys
import numpy as np

import time

from thorlabs_tsi_sdk.tl_camera import TLCameraSDK

# Import fitting libraries.

# Numpy fitter, this should always be available.
import storm_control.sc_hardware.utility.np_lock_peak_finder as npLPF

# Finding using the storm-analysis project, fitting using image correlation.
cl2DG = None
try:
    import storm_control.sc_hardware.utility.corr_lock_c2dg as cl2DG
except ModuleNotFoundError as mnfe:
    # Only need one warning about the lack of storm-analysis.
    pass
except OSError as ose:
    print(">> Warning! Correlation lock fitting C library not found. <<")
    print(ose)
    pass


# Helper functions
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

class CameraInfo:
    def __init__(self, nMaxWidth, nMaxHeight):
        self.nMaxWidth = nMaxWidth
        self.nMaxHeight = nMaxHeight

class Camera:
    """
    UC480 Camera Interface Class
    """
    def __init__(self, camera_id, dll_location: str):
        # Initialize the SDK
        dll_path_config(dll_location)
        self.sdk = TLCameraSDK()

        # TODO: Grab info from the camera
        self.info = CameraInfo(1440, 1080)

        # Try to find the camera
        # TODO: Improve access beyond index
        available_cameras = self.sdk.discover_available_cameras()
        if len(available_cameras) < camera_id:
            raise 'ThorLabs camera at the given index not found'

        # Grab the camera
        self.camera = self.sdk.open_camera(available_cameras[camera_id])

        # Add in camera settings
        # TODO: Load in from settings file
        self.camera.exposure_time_us = 11000
        self.camera.frames_per_trigger_zero_for_unlimited = 0
        self.camera.image_poll_timeout_ms = 1000
        
        self.camera.roi = (700, 828, 875, 903)
        
        self.camera.arm(2)
        self.camera.issue_software_trigger()

    def captureImage(self):
        """
        Wait for the next frame from the camera, then call self.getImage().
        """
        return self.getImage()

    def captureImageTest(self):
        """
        For testing..
        """
        
    def getCameraStatus(self, status_code):
        return True

    def getImage(self):
        """
        Copy an image from the camera into self.data and return self.data
        """
        # TODO: Find out why after shutdown a frame is attempted to be captured
        if not self.sdk._is_sdk_open:
            return None
        frame = self.camera.get_pending_frame_or_null()
        if frame is None:
            # TODO: More cleanly handle failed frame grabs
            raise 'Failed to get a frame'
        return np.copy(frame.image_buffer)

    def getNextImage(self):
        """
        Waits until an image is available from the camera, then 
        call self.getImage() to return the new image.
        """
        return self.getImage()

    def getSensorInfo(self):
        return self.info

    def getTimeout(self):
        return 1

    def loadParameters(self, filename):
        return None

    def saveParameters(self, filename):
        """
        Save the current camera settings to a file.
        """

    def setAOI(self, x_start, y_start, width, height):
        # x and y start have to be multiples of 2.
        # self.camera.roi = (x_start, y_start, width, height)
        return None

    def setBuffers(self):
        """
        Based on the AOI, create the internal buffer that the camera will use and
        the intermediate buffer that we will copy the data from the camera into.
        """

    def setFrameRate(self, frame_rate = 1000, verbose = False):
        return None

    def setPixelClock(self, pixel_clock_MHz):
        """
        43MHz seems to be the max for this camera?
        """

    def setTimeout(self, timeout):
        return None

    def shutDown(self):
        """
        Shut down the camera.
        """
        self.camera.dispose()
        self.sdk.dispose()

    def startCapture(self):
        """
        Start video capture (as opposed to single frame capture, which is done with self.captureImage().
        """

    def stopCapture(self):
        """
        Stop video capture.
        """


class CameraQPD(object):
    """
    QPD emulation class. The default camera ROI of 200x200 pixels.
    The focus lock is configured so that there are two laser spots on the camera.
    The distance between these spots is fit and the difference between this distance and the
    zero distance is returned as the focus lock offset. The maximum value of the camera
    pixels is returned as the focus lock sum.
    """
    def __init__(self,
                 allow_single_fits = False,
                 background = None,                 
                 camera_id = 1,
                 ini_file = None,
                 offset_file = None,
                 pixel_clock = None,
                 sigma = None,
                 x_width = None,
                 y_width = None,
                 **kwds):
        super().__init__(**kwds)

        self.allow_single_fits = allow_single_fits
        self.background = background
        self.fit_mode = 1
        self.fit_size = int(1.5 * sigma)
        self.image = None
        self.last_power = 0
        self.offset_file = offset_file
        self.sigma = sigma
        self.x_off1 = 0.0
        self.y_off1 = 0.0
        self.x_off2 = 0.0
        self.y_off2 = 0.0
        self.zero_dist = 0.5 * x_width

        # Add path information to files that should be in the same directory.
        ini_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ini_file)

        # Open camera
        self.cam = Camera(0, 'C:\\Users\\RPI\\Desktop\\AlgoBioLab\\ThorLabsDLL')

        # Set timeout
        self.cam.setTimeout(1)

        # Set camera AOI x_start, y_start.
        with open(self.offset_file) as fp:
            [self.x_start, self.y_start] = map(int, fp.readline().split(",")[:2])

        # Set camera AOI.
        self.x_width = x_width
        self.y_width = y_width
        print(self.x_width, self.y_width)
        self.setAOI()

        # Run at maximum speed.
        self.cam.setPixelClock(pixel_clock)
        self.cam.setFrameRate(verbose = True)

        # Some derived parameters
        self.half_x = int(self.x_width/2)
        self.half_y = int(self.y_width/2)
        self.X = numpy.arange(self.y_width) - 0.5*float(self.y_width)

    def adjustAOI(self, dx, dy):
        self.x_start += dx
        self.y_start += dy
        if(self.x_start < 0):
            self.x_start = 0
        if(self.y_start < 0):
            self.y_start = 0
        if((self.x_start + self.x_width + 2) > self.cam.info.nMaxWidth):
            self.x_start = self.cam.info.nMaxWidth - (self.x_width + 2)
        if((self.y_start + self.y_width + 2) > self.cam.info.nMaxHeight):
            self.y_start = self.cam.info.nMaxHeight - (self.y_width + 2)
        self.setAOI()

    def adjustZeroDist(self, inc):
        self.zero_dist += inc

    def capture(self):
        """
        Get the next image from the camera.
        """
        self.image = self.cam.captureImage()
        return self.image

    def changeFitMode(self, mode):
        """
        mode 1 = gaussian fit, any other value = first moment calculation.
        """
        self.fit_mode = mode

    def doMoments(self, data):
        """
        Perform a moment based calculation of the distances.
        """
        self.x_off1 = 1.0e-6
        self.y_off1 = 0.0
        self.x_off2 = 1.0e-6
        self.y_off2 = 0.0

        total_good = 0
        data_band = data[self.half_y-15:self.half_y+15,:]

        # Moment for the object in the left half of the picture.
        x = numpy.arange(self.half_x)
        data_ave = numpy.average(data_band[:,:self.half_x], axis = 0)
        power1 = numpy.sum(data_ave)

        dist1 = 0.0
        if (power1 > 0.0):
            total_good += 1
            self.y_off1 = numpy.sum(x * data_ave) / power1 - self.half_x
            dist1 = abs(self.y_off1)

        # Moment for the object in the right half of the picture.
        data_ave = numpy.average(data_band[:,self.half_x:], axis = 0)
        power2 = numpy.sum(data_ave)

        dist2 = 0.0
        if (power2 > 0.0):
            total_good += 1
            self.y_off2 = numpy.sum(x * data_ave) / power2
            dist2 = abs(self.y_off2)

        # The moment calculation is too fast. This is to slow things
        # down so that (hopefully) the camera doesn't freeze up.
        time.sleep(0.02)
        
        return [total_good, dist1, dist2]

    def getImage(self):
        return [self.image, self.x_off1, self.y_off1, self.x_off2, self.y_off2, self.sigma]

    def getZeroDist(self):
        return self.zero_dist

    def qpdScan(self, reps = 4):
        """
        Returns [power, offset, is_good]
        """
        power_total = 0.0
        offset_total = 0.0
        good_total = 0.0
        for i in range(reps):
            [power, n_good, offset] = self.singleQpdScan()
            power_total += power
            good_total += n_good
            offset_total += offset
            
        power_total = power_total/float(reps)
        if (good_total > 0):
            return [power_total, offset_total/good_total, True]
        else:
            return [power_total, 0, False]

    def setAOI(self):
        """
        Set the camera AOI to current AOI.
        """
        self.cam.setAOI(self.x_start,
                        self.y_start,
                        self.x_width,
                        self.y_width)

    def shutDown(self):
        """
        Save the current camera AOI location and offset. Shutdown the camera.
        """
        if self.offset_file:
            with open(self.offset_file, "w") as fp:
                fp.write(str(self.x_start) + "," + str(self.y_start))
        self.cam.shutDown()

    def singleQpdScan(self):
        """
        Perform a single measurement of the focus lock offset and camera sum signal.

        Returns [power, total_good, offset]
        """
        data = self.capture().copy()

        # The power number is the sum over the camera AOI minus the background.
        power = numpy.sum(data.astype(numpy.int64)) - self.background
        
        # (Simple) Check for duplicate frames.
        if (power == self.last_power):
            #print("> UC480-QPD: Duplicate image detected!")
            time.sleep(0.05)
            return [self.last_power, 0, 0]

        self.last_power = power

        # Determine offset by fitting gaussians to the two beam spots.
        # In the event that only beam spot can be fit then this will
        # attempt to compensate. However this assumes that the two
        # spots are centered across the mid-line of camera ROI.
        #
        if (self.fit_mode == 1):
            [total_good, dist1, dist2] = self.doFit(data)

        # Determine offset by moments calculation.
        else:
            [total_good, dist1, dist2] = self.doMoments(data)
                        
        # Calculate offset.
        #

        # No good fits.
        if (total_good == 0):
            return [power, 0.0, 0.0]

        # One good fit.
        elif (total_good == 1):
            if self.allow_single_fits:
                return [power, 1.0, ((dist1 + dist2) - 0.5*self.zero_dist)]
            else:
                return [power, 0.0, 0.0]

        # Two good fits. This gets twice the weight of one good fit
        # if we are averaging.
        else:
            return [power, 2.0, 2.0*((dist1 + dist2) - self.zero_dist)]

            
class CameraQPDScipyFit(CameraQPD):
    """
    This version uses scipy to do the fitting.
    """
    def __init__(self, fit_mutex = False, **kwds):
        super().__init__(**kwds)

        self.fit_mutex = fit_mutex

    def doFit(self, data):
        dist1 = 0
        dist2 = 0
        self.x_off1 = 0.0
        self.y_off1 = 0.0
        self.x_off2 = 0.0
        self.y_off2 = 0.0

        # numpy finder/fitter.
        #
        # Fit first gaussian to data in the left half of the picture.
        total_good =0
        [max_x, max_y, params, status] = self.fitGaussian(data[:,:self.half_x])
        if status:
            total_good += 1
            self.x_off1 = float(max_x) + params[2] - self.half_y
            self.y_off1 = float(max_y) + params[3] - self.half_x
            dist1 = abs(self.y_off1)

        # Fit second gaussian to data in the right half of the picture.
        [max_x, max_y, params, status] = self.fitGaussian(data[:,-self.half_x:])
        if status:
            total_good += 1
            self.x_off2 = float(max_x) + params[2] - self.half_y
            self.y_off2 = float(max_y) + params[3]
            dist2 = abs(self.y_off2)

        return [total_good, dist1, dist2]
        
    def fitGaussian(self, data):
        if (numpy.max(data) < 25):
            return [False, False, False, False]
        x_width = data.shape[0]
        y_width = data.shape[1]
        max_i = data.argmax()
        max_x = int(max_i/y_width)
        max_y = int(max_i%y_width)
        if (max_x > (self.fit_size-1)) and (max_x < (x_width - self.fit_size)) and (max_y > (self.fit_size-1)) and (max_y < (y_width - self.fit_size)):
            if self.fit_mutex:
                self.fit_mutex.lock()
            #[params, status] = npLPF.fitSymmetricGaussian(data[max_x-self.fit_size:max_x+self.fit_size,max_y-self.fit_size:max_y+self.fit_size], 8.0)
            #[params, status] = npLPF.fitFixedEllipticalGaussian(data[max_x-self.fit_size:max_x+self.fit_size,max_y-self.fit_size:max_y+self.fit_size], 8.0)
            [params, status] = npLPF.fitFixedEllipticalGaussian(data[max_x-self.fit_size:max_x+self.fit_size,max_y-self.fit_size:max_y+self.fit_size], self.sigma)
            if self.fit_mutex:
                self.fit_mutex.unlock()
            params[2] -= self.fit_size
            params[3] -= self.fit_size
            return [max_x, max_y, params, status]
        else:
            return [False, False, False, False]

# Testing
if (__name__ == "__main__"):
    camera = Camera(0, 'C:\\Users\\RPI\\Desktop\\AlgoBioLab\\ThorLabsDLL')
    camera.getImage()

    camera.shutDown()

#
# The MIT License
#
# Copyright (c) 2013 Zhuang Lab, Harvard University
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
