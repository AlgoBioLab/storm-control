import abc
import numpy as np
from typing import Tuple

class Camera(metaclass=abc.ABCMeta):
    """
    The interface which is used for describing the functionality of a camera
    being used for QPD emulation
    """

    @abc.abstractmethod
    def getImage(self) -> np.ndarray:
        """
        Wait for a new frame from the camera and return the data as a numpy
        array.

        The frame dimensions are determined by the AOI being captured for.
        Additionally, the values should be grayscale between 0-255.

        If a new frame is not captured by "timeout", and expection is thrown.
        """
        pass

    @abc.abstractmethod
    def getTimeout(self) -> float:
        """ Get the current timeout set for the camera. Timeout is in seconds """
        pass

    @abc.abstractmethod
    def setTimeout(self, timeout: float) -> None:
        """ Set the timeout for capturing a frame. Timeout is in second """
        pass

    @abc.abstractmethod
    def getAOI(self) -> Tuple[int, int, int, int]:
        """ Get the area of interest the camera is capturing for, (x_start, y_start, width, height) """
        pass

    @abc.abstractmethod
    def setAOI(self, x_start: int, y_start: int, width: int, height: int) -> None:
        """ Set the area of interest the camera is capturing for """
        pass

    @abc.abstractmethod
    def shutdown(self) -> None:
        """
        Camera specific cleanup logic, assumed that the camera is not
        usable after a shutdown call and a new instance would need to
        be created
        """
        pass
