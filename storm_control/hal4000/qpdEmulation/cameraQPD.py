import abc
import numpy as np
from typing import Tuple, Union
import os
from PyQt5 import QtCore
import time

from storm_control.hal4000.halLib.halFunctionality import HalFunctionality
from storm_control.hal4000.halLib.halModule import HalModule
import storm_control.sc_hardware.baseClasses.hardwareModule as hardwareModule
import storm_control.sc_hardware.baseClasses.lockModule as lockModule
import storm_control.hal4000.halLib.halMessage as halMessage
import storm_control.sc_hardware.utility.np_lock_peak_finder as npLPF


class Camera(hardwareModule.HardwareModule, HalFunctionality): # metaclass=abc.ABCMeta):
    """
    The interface which is used for describing the functionality of a camera
    being used for QPD emulation
    """
    def __init__(self, module_params = None, qt_settings = None, **kwds):
        super().__init__(**kwds)

    #@abc.abstractmethod
    def getImage(self) -> np.ndarray:
        """
        Wait for a new frame from the camera and return the data as a numpy
        array.

        The frame dimensions are determined by the AOI being captured for.
        Additionally, the values should be grayscale between 0-255.

        If a new frame is not captured by "timeout", and expection is thrown.
        """
        return np.ndarray([])

    #@abc.abstractmethod
    def getTimeout(self) -> float:
        """ Get the current timeout set for the camera. Timeout is in seconds """
        return 0.0

    #@abc.abstractmethod
    def setTimeout(self, timeout: float) -> None:
        """ Set the timeout for capturing a frame. Timeout is in second """
        pass

    #@abc.abstractmethod
    def getAOI(self) -> Tuple[int, int, int, int]:
        """ Get the area of interest the camera is capturing for, (x_start, y_start, width, height) """
        return(1, 1, 1, 1)

    #@abc.abstractmethod
    def setAOI(self, x_start: int, y_start: int, width: int, height: int) -> None:
        """ Set the area of interest the camera is capturing for """
        pass

    #@abc.abstractmethod
    def shutdown(self) -> None:
        """
        Camera specific cleanup logic, assumed that the camera is not
        usable after a shutdown call and a new instance would need to
        be created
        """
        pass

    def processMessage(self, message):
        if message.isType('get functionality') and message.getData()['name'] == self.module_name:
            message.addResponse(halMessage.HalMessageResponse(source=self.module_name, data={'functionality': self}))


class CameraQPDScanThread(QtCore.QThread):
    """
    Handles periodic polling of the camera to determine the current offset.
    In testing this approach appeared more performant than starting a new
    QRunnable for each scan.
    """
    def __init__(self, camera, qpd_update_signal, reps, units_to_microns):
        self.camera = camera
        self.qpd_update_signal = qpd_update_signal
        self.reps = reps
        self.units_to_microns = units_to_microns
        self.running = False

    def isRunning(self) -> bool:
        return self.running

    def run(self) -> None:
        self.running = True
        while (self.running):
            # Capture a scan
            [power, offset, is_good] = self.camera.qpdScan(reps = self.reps)

            # Get the intermediate results from the scane

            # Emit the results
            pass

    def startScan(self) -> None:
        self.start(QtCore.QThread.NormalPriority)

    def stopScan(self) -> None:
        self.running = False
        self.wait()


class CameraQPD(hardwareModule.HardwareModule, lockModule.QPDCameraFunctionalityMixin):
    """
    Exposes the QPD emulation via camera to the rest of the system. This class
    takes in the camera hardware interface and fit approch and handles
    combining the logic.

    :ivar camera: The hardware interface to the camera being used
    :ivar camera_module: Name of the camera module as defined in the XML config
    :ivar fit_approach: The fit method that operates on camera frames
    :ivar fit_module: Name of the fit module as defined in the XML config
    :ivar aoi_width: The width of the area of interest of the camera frame
    :ivar aoi_height: The height of the area of interest of the camera frame
    :ivar offset_file_location: Location of AOI start coordinate file. File
        should contain the x,y coordinate as in the example "756,800"
    :ivar aoi_x_start: The starting x coordinate of the AOI
    :ivar aoi_y_start: The starting y coordinate of the AOI
    :ivar qpdUpdate: Signal used to share new QPD data outside of this class
    :ivar thread_update: Signal used to get QPD data from the QPD thread
    """
    CAMERA_MODULE_ERROR = 'Configuration has not completed successfully, camera for QPD emulation not found'
    FIT_MODULE_ERROR = 'Configuration has not completed successfully, fit approach for QPD emulation not found'


    def __init__(self, module_params = None, qt_settings = None, **kwds):
        super().__init__(**kwds)
        # Module parameters provided when constructing the module
        assert module_params is not None

        configuration = module_params.get("configuration")

        # Grab the camera module
        self.camera: Union[Camera, None] = None
        self.camera_module: str = configuration.get('camera', None)
        if self.camera_module is None:
            raise Exception('Camera object not provided to CameraQPD')

        # Grab the fit module
        self.fit_approach: Union[None, CameraQPDFit]  = None
        self.fit_module: str = configuration.get('fit', None)
        if self.fit_module is None:
            raise Exception('Fit module not provided to CameraQPD')

        # Get the width and height of the AOI
        self.aoi_width: int = configuration.get('aoi_width', None)
        self.aoi_height: int = configuration.get('aoi_heigth', None)
        if self.aoi_width is None or self.aoi_height is None:
            raise Exception('AOI width and height required')

        # Get the AOI starting x and y positions
        self.offset_file_location: str = configuration.get('offset_file', None)
        if self.offset_file_location is None:
            raise Exception('Provide an offset file to the CameraQPD to handle AOI')
        if not os.path.isfile(self.offset_file_location):
            raise Exception('Provided offset file location is not accessible: {}'.format(self.offset_file_location))
        self.aoi_x_start = 0
        self.aoi_y_start = 0
        with open(self.offset_file_location, 'r') as offset_file:
            self.aoi_x_start, self.aoi_y_start = offset_file.readline().split(',')[:2]

        # Setup signals for QPD update emissions
        self.qpdUpdate = QtCore.pyqtSignal(dict)
        self.thread_update = QtCore.pyqtSignal(dict)
        self.thread_update.connect(self.handleThreadUpdate)

    def handleResponse(self, message, response) -> None:
        if message.isType('get functionality') and response.source == self.camera_module:
            self.camera = response.getData()['functionality']
        elif message.isType('get functionality') and response.source == self.fit_module:
            self.fit_approach = response.getData()['functionality']

        # If the camera and fit approach are now defined, create thread
        if self.camera and self.fit_approach:
            self.startQPDThread()

    def processMessage(self, message) -> None:
        if message.isType('configuration'):
            # Request the camera object
            self.sendMessage(halMessage.HalMessage(m_type='get functionality',
                                                   data={ 'name': self.camera_module }))
            # Request the fit object
            self.sendMessage(halMessage.HalMessage(m_type='get functionality',
                                                   data={ 'name': self.fit_module }))

    def startQPDThread(self) -> None:
        # Create the thread
        # TODO: Get the value for reps, and units_to_microns
        self.scan_thread = CameraQPDScanThread(self.camera, self.thread_update, 10, 10)

    def qpdScan(self, reps=4) -> Tuple[float, float, bool]:
        assert self.camera is not None, CameraQPD.CAMERA_MODULE_ERROR
        assert self.fit_approach is not None, CameraQPD.FIT_MODULE_ERROR

        power_total = 0.0
        offset_total = 0.0
        good_total = 0.0
        for _ in range(reps):
            [power, n_good, offset] = self.fit_approach.singleQpdScan(self.camera.getImage())
            power_total += power
            good_total += n_good
            offset_total += offset

        power_total = power_total/float(reps)
        if (good_total > 0):
            return tuple([power_total, offset_total/good_total, True])
        else:
            return tuple([power_total, 0, False])

    def handleThreadUpdate(self, qpd_dict: dict) -> None:
        #
        # Why are we doing this? In testing we found that bouncing the update signal
        # from the scan_thread through this class meant we could sample about twice
        # as fast as having scan_thread directly emit the qpdUpdate() signal. It is
        # not that clear why this should be the case. Perhaps signals are not buffered
        # so scan_thread was having to wait for the focus lock control / GUI to
        # process the signal before it could start on the next sample?
        #
        self.qpdUpdate.emit(qpd_dict)

    # QPDCameraFunctionalityMixin
    def adjustAOI(self, dx, dy):
        assert self.camera is not None, CameraQPD.CAMERA_MODULE_ERROR
        pass

    def adjustZeroDist(self, inc) -> None:
        pass

    def changeFitMode(self, mode) -> None:
        pass

    def getMinimumInc(self) -> int:
        return 0

    def getOffset(self):
        #
        # lockControl.LockControl will call this each time the qpdUpdate signal
        # is emitted, but we only want the thread to get started once.
        #
        if not self.scan_thread.isRunning():
            self.scan_thread.startScan()

    def getFunctionality(self, message):
        if (message.getData()["name"] == self.module_name):
            print(message.source)
            message.addResponse(halMessage.HalMessageResponse(source = self.module_name,
                                                              data = {"functionality" : self}))


class CameraQPDFit(HalModule, HalFunctionality):
    """ Interface which descibes how fit implementations function """
    def __init__(self, module_params = None, qt_settings = None, **kwds):
        super().__init__(**kwds)

    @abc.abstractmethod
    def doFit(self, data: np.ndarray) -> Tuple:
        pass

    def singleQpdScan(self, image: np.ndarray):
        """
        Perform a single measurement of the focus lock offset and camera sum signal.

        Returns [power, total_good, offset]
        """
        assert self.camera is not None, CameraQPD.CAMERA_MODULE_ERROR

        # The power number is the sum over the camera AOI minus the background.
        power = np.sum(image.astype(np.int64)) - self.background

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
            [total_good, dist1, dist2] = self.doFit(image)

        # Determine offset by moments calculation.
        else:
            [total_good, dist1, dist2] = self.doMoments(image)

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

    def processMessage(self, message):
        if message.isType('get functionality') and message.getData()['name'] == self.module_name:
            message.addResponse(halMessage.HalMessageResponse(source=self.module_name, data={'functionality': self}))



class CameraQPDScipyFit(CameraQPDFit):
    """
    QPD Fit based on leveraging scipy. This implementation can be originally
    found in
    `storm_control/sc_hardware/thorlabs/uc480Camera.py`
    """
    def __init__(self, fit_mutex = None, **kwds):
        super().__init__(**kwds)

        self.fit_mutex = fit_mutex

    def doFit(self, data) -> Tuple:
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

        return (total_good, dist1, dist2)

    def fitGaussian(self, data):
        if (np.max(data) < 25):
            return [False, False, False, False]
        x_width = data.shape[0]
        y_width = data.shape[1]
        max_i = data.argmax()
        max_x = int(max_i/y_width)
        max_y = int(max_i%y_width)
        if (max_x > (self.fit_size-1)) and (max_x < (x_width - self.fit_size)) and (max_y > (self.fit_size-1)) and (max_y < (y_width - self.fit_size)):
            if self.fit_mutex is not None:
                self.fit_mutex.lock()
            [params, status] = npLPF.fitFixedEllipticalGaussian(data[max_x-self.fit_size:max_x+self.fit_size,max_y-self.fit_size:max_y+self.fit_size], self.sigma)
            if self.fit_mutex:
                self.fit_mutex.unlock()
            params[2] -= self.fit_size
            params[3] -= self.fit_size
            return [max_x, max_y, params, status]
        else:
            return [False, False, False, False]
