import abc
import numpy as np

from storm_control.hal4000.halLib.halModule import HalModule
from storm_control.hal4000.halLib.halFunctionality import HalFunctionality
import storm_control.hal4000.halLib.halMessage as halMessage
import storm_control.sc_hardware.utility.np_lock_peak_finder as npLPF


class CameraQPDFitResults:
    def __init__(self, power, total_good, offset, dist1, dist2, image, x_off1,
                 y_off1, x_off2, y_off2, sigma):
        """
        :type power: float
        :type total_good: float
        :type offset: float
        :type dist1: float
        :type dist2: float
        :type image: np.ndarray
        :type x_off1: float
        :type y_off1: float
        :type x_off2: float
        :type y_off2: float
        :type sigma: float
        """
        self.power = power
        self.total_good = total_good
        self.offset = offset
        self.dist1 = dist1
        self.dist2 = dist2
        self.image = image
        self.x_off1 = x_off1
        self.y_off1 = y_off1
        self.x_off2 = x_off2
        self.y_off2 = y_off2
        self.sigma = sigma


class FitIntemediateResults:
    def __init__(self, total_good, dist1, dist2, x_off1, y_off1,
                 x_off2, y_off2):
        """
        :type total_good: int
        :type dist1: float
        :type dist2: float
        :type x_off1: float
        :type y_off1: float
        :type x_off2: float
        :type y_off2: float
        """
        self.total_good = total_good
        self.dist1 = dist1
        self.dist2 = dist2
        self.x_off1 = x_off1
        self.y_off1 = y_off1
        self.x_off2 = x_off2
        self.y_off2 = y_off2


class CameraQPDFit(HalModule, HalFunctionality):
    """ Interface which descibes how fit implementations function """
    def __init__(self, module_params=None, qt_settings=None, **kwds):
        super().__init__(**kwds)
        self.last_power = 0.0

        configuration = module_params.get('configuration')

        self.sigma = configuration.get('sigma')
        self.background = configuration.get('background')
        self.zero_dist = configuration.get('zero_dist')
        self.allow_single_fits = configuration.get('allow_single_fits')

    @abc.abstractmethod
    def doFit(self, data: np.ndarray) -> FitIntemediateResults:
        pass

    def singleQpdScan(self, image):
        """
        Perform a single measurement of the focus lock offset and camera sum
        signal.

        :type image: np.ndarray
        :rtype: CameraQPDFitResults
        """
        # The power number is the sum over the camera AOI minus the background.
        power = float(np.sum(image.astype(np.int64)) - self.background)

        # (Simple) Check for duplicate frames.
        '''
        if (power == self.last_power):
            print("> UC480-QPD: Duplicate image detected!")
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
        '''

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
                offset = ((fit_intermediate.dist1 + fit_intermediate.dist2) -
                          0.5*self.zero_dist)
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
            offset = 2.0*((fit_intermediate.dist1 + fit_intermediate.dist2) -
                          self.zero_dist)
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
        is_target_functionality = message.isType('get functionality') and \
                message.getData()['name'] == self.module_name
        if is_target_functionality:
            data = {'functionality': self}
            response = halMessage.HalMessageResponse(source=self.module_name,
                                                     data=data)
            message.addResponse(response)


class CameraQPDScipyFit(CameraQPDFit):
    """
    QPD Fit based on leveraging scipy. This implementation can be originally
    found in
    `storm_control/sc_hardware/thorlabs/uc480Camera.py`
    """
    class GaussianResult:
        def __init__(self, max_x, max_y, params, status):
            """
            :type max_x: float
            :type max_y: float
            :type params: object
            :type status: bool
            """
            self.max_x = max_x
            self.max_y = max_y
            self.params = params
            self.status = status

    def __init__(self, fit_mutex=None, **kwds):
        super().__init__(**kwds)

        self.fit_mutex = fit_mutex

        self.fit_size = int(1.5 * self.sigma)

    def doFit(self, data):
        """
        :rtype: FitIntemediateResults
        """
        dist1 = 0
        dist2 = 0

        x_off1 = 0.0
        y_off1 = 0.0
        x_off2 = 0.0
        y_off2 = 0.0

        x_width, y_width = data.shape
        half_x = int(x_width / 2)
        half_y = int(y_width / 2)

        # numpy finder/fitter.
        #
        # Fit first gaussian to data in the left half of the picture.
        total_good = 0
        gaussian_result = self.fitGaussian(data[:, :half_x])
        if gaussian_result.status:
            total_good += 1
            x_off1 = float(gaussian_result.max_x) + gaussian_result.params[2] \
                - half_y
            y_off1 = float(gaussian_result.max_y) + gaussian_result.params[3] \
                - half_x
            dist1 = abs(y_off1)

        # Fit second gaussian to data in the right half of the picture.
        gaussian_result = self.fitGaussian(data[:, -half_x:])
        if gaussian_result.status:
            total_good += 1
            x_off2 = float(gaussian_result.max_x) + gaussian_result.params[2] \
                - half_y
            y_off2 = float(gaussian_result.max_y) + gaussian_result.params[3]
            dist2 = abs(y_off2)

        return FitIntemediateResults(total_good, dist1, dist2, x_off1, y_off1,
                                     x_off2, y_off2)

    def fitGaussian(self, data):
        """
        :rtype: GaussianResult
        """
        if (np.max(data) < 25):
            return CameraQPDScipyFit.GaussianResult(0.0, 0.0, None, False)
        x_width = data.shape[0]
        y_width = data.shape[1]
        max_i = data.argmax()
        max_x = int(max_i / y_width)
        max_y = int(max_i % y_width)
        if (max_x > (self.fit_size-1)) and \
                (max_x < (x_width - self.fit_size)) and \
                (max_y > (self.fit_size-1)) and \
                (max_y < (y_width - self.fit_size)):
            if self.fit_mutex is not None:
                self.fit_mutex.lock()
            [params, status] = npLPF.fitFixedEllipticalGaussian(
                    data[max_x - self.fit_size:max_x+self.fit_size,
                         max_y-self.fit_size:max_y+self.fit_size], self.sigma)
            if self.fit_mutex:
                self.fit_mutex.unlock()
            params[2] -= self.fit_size
            params[3] -= self.fit_size
            return CameraQPDScipyFit.GaussianResult(max_x, max_y, params,
                                                    status)
        else:
            return CameraQPDScipyFit.GaussianResult(0.0, 0.0, None, False)
