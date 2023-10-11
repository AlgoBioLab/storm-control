from typing import Union
import os
from PyQt5 import QtCore

import storm_control.sc_hardware.baseClasses.hardwareModule as hardwareModule
import storm_control.sc_hardware.baseClasses.lockModule as lockModule
import storm_control.hal4000.halLib.halMessage as halMessage
from storm_control.hal4000.qpdEmulation.cameraInterface import Camera
from storm_control.hal4000.qpdEmulation.cameraQPDFit import CameraQPDFit, CameraQPDFitResults


class CameraQPDScanThread(QtCore.QThread):
    """
    Handles periodic polling of the camera to determine the current offset.
    In testing this approach appeared more performant than starting a new
    QRunnable for each scan.
    """
    def __init__(self, camera: Camera, fit: CameraQPDFit, qpd_update_signal, reps, units_to_microns):
        super().__init__()
        self.camera = camera
        self.fit = fit
        self.qpd_update_signal = qpd_update_signal
        self.reps = reps
        self.units_to_microns = units_to_microns
        self.running = False

    def isRunning(self) -> bool:
        return self.running

    def run(self) -> None:
        self.running = True
        while (self.running):
            # Capture the results
            fit_result = self.qpdScan(reps = self.reps)

            # Emit the results
            result_dict = {
                'is_good': fit_result.total_good > 0,
                'image': fit_result.image,
                'offset': fit_result.offset * self.units_to_microns,
                'sigma': fit_result.sigma,
                'sum': fit_result.power,
                'x_off1': fit_result.x_off1,
                'y_off1': fit_result.y_off1,
                'x_off2': fit_result.x_off2,
                'y_off2': fit_result.y_off2
            }
            self.qpd_update_signal.emit(result_dict)


    def qpdScan(self, reps=4) -> CameraQPDFitResults:
        """
        Handles executing a series of scans with the average power is
        computed over. This is a legacy component from the previous QPD
        implemented from the UC480 code. The average calcualation would
        ideally be separated from the thread, but the for loop requires
        repeated calls to `singleQPDScan`. In order to decouple the fit logic
        and camera logic, this approach was maintained so that an image
        can be passed directly to the fit logic.
        """
        assert reps > 0, 'Number of reps must be greater then 0'

        power_total = 0.0
        offset_total = 0.0
        good_total = 0.0
        most_recent_result = None

        for _ in range(reps):
            # Make the single fit request
            fit_result = self.fit.singleQpdScan(self.camera.getImage())

            # Calcualte the aggregate results
            power_total += fit_result.power
            good_total += fit_result.total_good
            offset_total += fit_result.offset

            # Update the most recent result
            most_recent_result = fit_result

        assert most_recent_result is not None, 'Error QPD scans unexpectedly did not produce any results'

        power_total = power_total/float(reps)
        if good_total > 0:
            return CameraQPDFitResults(
                power_total,
                good_total,
                offset_total,
                most_recent_result.dist1,
                most_recent_result.dist2,
                most_recent_result.image.copy(),
                most_recent_result.x_off1,
                most_recent_result.y_off1,
                most_recent_result.x_off2,
                most_recent_result.y_off2,
                most_recent_result.sigma
            )
        else:
            return CameraQPDFitResults(
                power_total,
                0.0,
                0.0,
                0.0,
                0.0,
                most_recent_result.image.copy(),
                0.0,
                0.0,
                0.0,
                0.0,
                most_recent_result.sigma
            )

    def startScan(self) -> None:
        self.start(QtCore.QThread.Priority.NormalPriority)

    def stopScan(self) -> None:
        self.running = False
        self.wait()


class CameraQPD(hardwareModule.HardwareModule, lockModule.QPDCameraFunctionalityMixin, hardwareModule.HardwareFunctionality):
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

    qpdUpdate = QtCore.pyqtSignal(dict)
    thread_update = QtCore.pyqtSignal(dict)


    def __init__(self, module_params = None, qt_settings = None, **kwds):
        super().__init__(**kwds)
        # Module parameters provided when constructing the module
        assert module_params is not None

        configuration = module_params.get('configuration')
        self.parameters = configuration.get('parameters')

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
        self.aoi_height: int = configuration.get('aoi_height', None)
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

        self.units_to_microns = configuration.get('units_to_microns')
        self.reps = configuration.get('reps')

        # Setup signals for QPD update emissions
        self.thread_update.connect(self.handleThreadUpdate)

        self.device_mutex = QtCore.QMutex()

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
        if message.isType('get functionality'):
            self.getFunctionality(message)

    def startQPDThread(self) -> None:
        # Create the thread
        assert self.camera is not None, 'Camera not defined'
        assert self.fit_approach is not None, 'Fit approach is not defined'

        self.scan_thread = CameraQPDScanThread(self.camera, self.fit_approach, self.thread_update, self.reps, self.units_to_microns)

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
            message.addResponse(halMessage.HalMessageResponse(source = self.module_name,
                                                              data = {"functionality" : self}))
