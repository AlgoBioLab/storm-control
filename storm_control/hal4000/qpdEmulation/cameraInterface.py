import numpy as np
from typing import Tuple

from storm_control.hal4000.halLib.halModule import HalModule
from storm_control.hal4000.halLib.halFunctionality import HalFunctionality
import storm_control.sc_hardware.baseClasses.hardwareModule as hardwareModule
import storm_control.hal4000.halLib.halMessage as halMessage


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
