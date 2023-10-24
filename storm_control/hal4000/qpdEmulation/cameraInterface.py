import numpy as np
import abc

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
        Get the area of interest the camera is capturing for (x_start, y_start, width, height)

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
        if message.isType('get functionality') and message.getData()['name'] == self.module_name:
            message.addResponse(halMessage.HalMessageResponse(source=self.module_name, data={'functionality': self}))



class CameraNone(Camera):
    """
    Implementation that will return two dots at a fixed distance apart
    """
    import cv2

    def __init__(self, module_params = None, qt_settings = None, **kwds):
        super().__init__(**kwds)
        assert module_params is not None

        self.timeout = 0.5

        # The actual AOI is not important in the camera emulation, the size
        # of the AOI is needed to generate the image
        self.aoi = (0, 0, 200, 200)
        self.dimensions = (200, 200)

        configuration = module_params.get('configuration')
        self.circle_radius = configuration.get('circule_radius', 5)
        self.circle_shade = configuration.get('circle_shade', 200)
        self.sigma = configuration.get('sigma', 5)


    def getImage(self):
        """
        Create an image with two gaussian blurs
        """
        # Make a black image
        image = np.full(self.dimensions, 0, dtype=np.uint8)

        # Make left circle
        left_center = (int(0.25 * self.dimensions[1]), int(0.5 * self.dimensions[0]))
        image = CameraNone.cv2.circle(image, left_center, self.circle_radius, (self.circle_shade,), -1)

        # Make right circle
        right_center = (int(0.75 * self.dimensions[1]), int(0.5 * self.dimensions[0]))
        image = CameraNone.cv2.circle(image, right_center, self.circle_radius, (self.circle_shade,), -1)

        # Blur the image
        image = CameraNone.cv2.GaussianBlur(image, (self.sigma, self.sigma), 0)

        return image

    def getTimeout(self):
        return self.timeout

    def setTimeout(self, timeout):
        self.timeout = timeout


    def getAOI(self):
        return self.aoi

    def setAOI(self, x_start, y_start, width, height):
        self.aoi = (x_start, y_start, width, height)
        self.dimensions = (height, width)

    def shutdown(self):
        pass

