import numpy as np
import abc

from storm_control.hal4000.halLib.halFunctionality import HalFunctionality
import storm_control.sc_hardware.baseClasses.hardwareModule as hardwareModule
import storm_control.hal4000.halLib.halMessage as halMessage


class Camera(hardwareModule.HardwareModule, HalFunctionality):
    """
    The interface which is used for describing the functionality of a camera
    being used for QPD emulation
    """
    def __init__(self, module_params=None, qt_settings=None, **kwds):
        super().__init__(**kwds)

    @abc.abstractmethod
    def getImage(self):
        """
        Wait for a new frame from the camera and return the data as a numpy
        array.

        The frame dimensions are determined by the AOI being captured for.
        Additionally, the values should be grayscale between 0-255.

        If a new frame is not captured by "timeout", and expection is thrown.

        :return: The numpy array representation of the image
        :rtype: np.ndarray
        """
        return np.ndarray([])

    @abc.abstractmethod
    def getTimeout(self):
        """
        Get the current timeout set for the camera. Timeout is in seconds

        :rtype: float
        """
        return 0.0

    @abc.abstractmethod
    def setTimeout(self, timeout):
        """
        Set the timeout for capturing a frame. Timeout is in second

        :param timeout: Timeout in seconds
        :type timeout: float
        :rtype: None
        """
        pass

    @abc.abstractmethod
    def getAOI(self):
        """
        Get the area of interest the camera is capturing for

        :return: (x_start, y_start, width, height)
        :rtype: Tuple[int, int, int, int]
        """
        return(1, 1, 1, 1)

    @abc.abstractmethod
    def setAOI(self, x_start, y_start, width, height):
        """
        Set the area of interest the camera is capturing for

        :type x_start: int
        :type y_start: int
        :type width: int
        :type height: int
        :rtype: None
        """
        pass

    @abc.abstractmethod
    def shutdown(self):
        """
        Camera specific cleanup logic, assumed that the camera is not
        usable after a shutdown call and a new instance would need to
        be created

        :rtype: None
        """
        pass

    def processMessage(self, message):
        is_target_functionality = message.isType('get functionality') and \
                message.getData()['name'] == self.module_name
        if is_target_functionality:
            data = {'functionality': self}
            response = halMessage.HalMessageResponse(source=self.module_name,
                                                     data=data)
            message.addResponse(response)
