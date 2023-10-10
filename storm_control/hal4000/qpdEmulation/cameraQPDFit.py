import time
import abc
from typing import Tuple
import numpy as np
from dataclasses import dataclass

from storm_control.hal4000.halLib.halModule import HalModule
from storm_control.hal4000.halLib.halFunctionality import HalFunctionality

@dataclass
class CameraQPDFitResults:
    power: float
    total_good: float
    offset: float
    dist1: float
    dist2: float
    image: np.ndarray
    x_off1: float
    y_off1: float
    x_off2: float
    y_off2: float
    sigma: float


@dataclass
class FitIntemediateResults:
    total_good: int
    dist1: float
    dist2: float
    x_off1: float
    y_off1: float
    x_off2: float
    y_off2: float


class CameraQPDFit(HalModule, HalFunctionality):
    """ Interface which descibes how fit implementations function """
    def __init__(self, module_params = None, qt_settings = None, **kwds):
        super().__init__(**kwds)
        self.last_power = 0.0

        # TODO: Grab the following values from config
        self.sigma = 0.0
        self.background = 0
        self.zero_dist = 0.0
        self.allow_single_fits = True

    @abc.abstractmethod
    def doFit(self, data: np.ndarray) -> FitIntemediateResults:
        pass

    def singleQpdScan(self, image: np.ndarray) -> CameraQPDFitResults:
        """
        Perform a single measurement of the focus lock offset and camera sum signal.

        Returns [power, total_good, offset]
        """
        # The power number is the sum over the camera AOI minus the background.
        power = float(np.sum(image.astype(np.int64)) - self.background)

        # (Simple) Check for duplicate frames.
        if (power == self.last_power):
            #print("> UC480-QPD: Duplicate image detected!")
            time.sleep(0.05)
            return CameraQPDFitResults(
                self.last_power,
                0.0,
                0.0,
                0.0,
                0.0,
                image,
                0.0,
                0.0,
                0.0,
                0.0,
                self.sigma
            )

        self.last_power = power

        fit_intermediate = self.doFit(image)

        # Calculate offset.
        #

        # No good fits.
        if (fit_intermediate.total_good == 0):
            return CameraQPDFitResults(
                power,
                0.0,
                0.0,
                0.0,
                0.0,
                image,
                0.0,
                0.0,
                0.0,
                0.0,
                self.sigma
            )

        # One good fit.
        elif (fit_intermediate.total_good == 1):
            if self.allow_single_fits:
                offset = ((fit_intermediate.dist1 + fit_intermediate.dist2) - 0.5*self.zero_dist)
                return CameraQPDFitResults(
                    power,
                    1.0,
                    offset,
                    fit_intermediate.dist1,
                    fit_intermediate.dist2,
                    image,
                    fit_intermediate.x_off1,
                    fit_intermediate.y_off1,
                    fit_intermediate.x_off2,
                    fit_intermediate.y_off2,
                    self.sigma
                )
            else:
                return CameraQPDFitResults(
                    power,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    image,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    self.sigma
                )

        # Two good fits. This gets twice the weight of one good fit
        # if we are averaging.
        else:
            offset = 2.0*((fit_intermediate.dist1 + fit_intermediate.dist2) - self.zero_dist)
            return CameraQPDFitResults(
                power,
                2.0,
                offset,
                fit_intermediate.dist1,
                fit_intermediate.dist2,
                image,
                fit_intermediate.x_off1,
                fit_intermediate.y_off1,
                fit_intermediate.x_off2,
                fit_intermediate.y_off2,
                self.sigma
            )

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
