from storm_control.hal4000.qpdEmulation.cameraInterface import Camera
import numpy as np
import cv2


class CameraNone(Camera):
    """
    Implementation that will return two dots at a fixed distance apart
    """

    def __init__(self, module_params=None, qt_settings=None, **kwds):
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
        left_center = (int(0.25 * self.dimensions[1]),
                       int(0.5 * self.dimensions[0]))
        image = cv2.circle(image, left_center, self.circle_radius,
                           (self.circle_shade,), -1)

        # Make right circle
        right_center = (int(0.75 * self.dimensions[1]),
                        int(0.5 * self.dimensions[0]))
        image = cv2.circle(image, right_center, self.circle_radius,
                           (self.circle_shade,), -1)

        # Blur the image
        image = cv2.GaussianBlur(image, (self.sigma, self.sigma), 0)

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
