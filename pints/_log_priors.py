#
# Defines different prior distributions
#
# This file is part of PINTS.
#  Copyright (c) 2017-2019, University of Oxford.
#  For licensing information, see the LICENSE file distributed with the PINTS
#  software package.
#
from __future__ import absolute_import, division
from __future__ import print_function, unicode_literals
import pints
import numpy as np
import scipy
import scipy.special
import scipy.stats


class BetaLogPrior(pints.LogPrior):
    r"""
    Defines a beta (log) prior with given shape parameters ``a`` and ``b``,
    with pdf

    .. math::
        f(x|a,b) = \frac{x^{a-1} (1-x)^{b-1}}{\mathrm{B}(a,b)}

    where :math:`\mathrm{B}` is the Beta function. A random variable :math:`X`
    distributed according to this pdf has expectation

    .. math::
        \mathrm{E}(X)=\frac{a}{a+b}.

    For example, to create a prior with shape parameters ``a=5`` and ``b=1``,
    use::

        p = pints.BetaLogPrior(5, 1)

    Extends :class:`LogPrior`.
    """
    def __init__(self, a, b):
        # Parse input arguments
        self._a = float(a)
        self._b = float(b)

        # Validate inputs
        if self._a <= 0:
            raise ValueError('Shape parameter a must be positive')
        if self._b <= 0:
            raise ValueError('Shape parameter b must be positive')

        # Cache constant
        self._log_beta = scipy.special.betaln(self._a, self._b)

    def __call__(self, x):
        if x[0] < 0.0 or x[0] > 1.0:
            return -np.inf
        else:
            return scipy.special.xlogy(self._a - 1.0,
                                       x[0]) + scipy.special.xlog1py(
                self._b - 1.0, -x[0]) - self._log_beta

    def cdf(self, x):
        """ See :meth:`LogPrior.cdf()`. """
        return scipy.stats.beta.cdf(x, self._a, self._b)

    def evaluateS1(self, x):
        """ See :meth:`LogPDF.evaluateS1()`. """
        value = self(x)
        _x = x[0]

        # Account for pathological edges
        if _x == 0.0:
            _x = np.nextafter(0.0, 1.0)
        elif _x == 1.0:
            _x = np.nextafter(1.0, 0.0)

        if _x < 0.0 or _x > 1.0:
            return value, np.asarray([0.])
        else:
            # Use np.divide here to better handle possible v small denominators
            return value, np.asarray([np.divide(self._a - 1., _x) - np.divide(
                self._b - 1., 1. - _x)])

    def icdf(self, p):
        """ See :meth:`LogPrior.icdf()`. """
        return scipy.stats.beta.ppf(p, self._a, self._b)

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return self._a / (self._a + self._b)

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return 1

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """
        return np.random.beta(self._a, self._b, size=(n, 1))


class CauchyLogPrior(pints.LogPrior):
    r"""
    Defines a 1-d Cauchy (log) prior with a given ``location``, and ``scale``,
    with pdf

    .. math::
        f(x|\text{location}, \text{scale}) = \frac{1}{\pi\;\text{scale}
        \left[1 + \left(\frac{x-\text{location}}{\text{scale}}\right)^2
        \right]}.

    A random variable distributed according to this pdf has undefined
    expectation.

    For example, to create a prior centered around 0 and a scale of 5, use::

        p = pints.CauchyLogPrior(0, 5)

    Extends :class:`LogPrior`.

    Parameters
    ----------
    location
        The center of the distribution.
    scale
        The scale of the distribution.
    """
    def __init__(self, location, scale):
        # Test inputs
        if float(scale) <= 0:
            raise ValueError('Scale must be positive')

        self._location = location
        self._scale = scale

        # Cache constants
        self._pi_sig = np.pi * self._scale
        self._pi_on_sig = np.pi / self._scale

    def __call__(self, x):
        _x_sq = (x[0] - self._location) * (x[0] - self._location)
        return -np.log(self._pi_sig + self._pi_on_sig * _x_sq)

    def cdf(self, x):
        """ See :meth:`LogPrior.cdf()`. """
        return scipy.stats.cauchy.cdf(x, self._location, self._scale)

    def icdf(self, p):
        """ See :meth:`LogPrior.icdf()`. """
        return scipy.stats.cauchy.ppf(p, self._location, self._scale)

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return np.nan

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return 1

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """
        return scipy.stats.cauchy.rvs(loc=self._location, scale=self._scale,
                                      size=(n, 1))


class ComposedLogPrior(pints.LogPrior):
    r"""
    N-dimensional LogPrior composed of one or more other Ni-dimensional
    LogPriors, such that ``sum(Ni) = N``. The evaluation of the composed
    log-prior assumes the input log-priors are all independent from each other.

    For example, a composed log prior::

        p = pints.ComposedLogPrior(log_prior1, log_prior2, log_prior3)

    where ``log_prior1``, 2, and 3 each have dimension 1 will have dimension 3
    itself.

    Extends :class:`LogPrior`.
    """
    def __init__(self, *priors):
        # Check if sub-priors given
        if len(priors) < 1:
            raise ValueError('Must have at least one sub-prior')

        # Check if proper priors, count dimension
        self._n_parameters = 0
        for prior in priors:
            if not isinstance(prior, pints.LogPrior):
                raise ValueError('All sub-priors must extend pints.LogPrior.')
            self._n_parameters += prior.n_parameters()

        # Store
        self._priors = priors

    def __call__(self, x):
        output = 0
        lo = hi = 0
        for prior in self._priors:
            lo = hi
            hi += prior.n_parameters()
            output += prior(x[lo:hi])
        return output

    def cdf(self, x):
        """
        See :meth:`LogPrior.cdf()`.

        *This method only works if the underlying :class:`LogPrior` classes all
        implement the optional method :class:`LogPDF.cdf().`.*
        """
        cdfs = []
        for i, prior in enumerate(self._priors):
            cdfs.append(prior.cdf(x[i]))
        return cdfs

    def evaluateS1(self, x):
        """
        See :meth:`LogPDF.evaluateS1()`.

        *This method only works if the underlying :class:`LogPrior` classes all
        implement the optional method :class:`LogPDF.evaluateS1().`.*
        """
        output = 0
        doutput = np.zeros(self._n_parameters)
        lo = hi = 0
        for prior in self._priors:
            lo = hi
            hi += prior.n_parameters()
            p, dp = prior.evaluateS1(x[lo:hi])
            output += p
            doutput[lo:hi] = np.asarray(dp)
        return output, doutput

    def icdf(self, x):
        """
        See :meth:`LogPrior.icdf()`.

        *This method only works if the underlying :class:`LogPrior` classes all
        implement the optional method :class:`LogPDF.icdf().`.*
        """
        icdfs = []
        for i, prior in enumerate(self._priors):
            icdfs.append(prior.icdf(x[i]))
        return icdfs

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return self._n_parameters

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """
        output = np.zeros((n, self._n_parameters))
        lo = hi = 0
        for prior in self._priors:
            lo = hi
            hi += prior.n_parameters()
            output[:, lo:hi] = prior.sample(n)
        return output

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return [prior.mean() for prior in self._priors]


class ExponentialLogPrior(pints.LogPrior):
    r"""
    Defines an exponential (log) prior with given rate parameter ``rate`` with
    pdf

    .. math::
        f(x|\text{rate}) = \text{rate} \; e^{-\text{rate}\;x}.

    A random variable :math:`X` distributed according to this pdf has
    expectation

    .. math::
        \mathrm{E}(X)=\frac{1}{\text{rate}}.

    For example, to create a prior with ``rate=0.5`` use::

        p = pints.ExponentialLogPrior(0.5)

    Extends :class:`LogPrior`.
    """
    def __init__(self, rate):
        # Parse input arguments
        self._rate = float(rate)

        # Validate inputs
        if self._rate <= 0:
            raise ValueError('Rate parameter "scale" must be positive')

        # Cache constant
        self._log_scale = np.log(self._rate)

    def __call__(self, x):
        if x[0] < 0.0:
            return -np.inf
        else:
            return self._log_scale - self._rate * x[0]

    def evaluateS1(self, x):
        """ See :meth:`LogPDF.evaluateS1()`. """
        value = self(x)

        if x[0] < 0.0:
            return value, np.asarray([0.])
        else:
            return value, np.asarray([-self._rate])

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return 1 / self._rate

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return 1

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """
        return np.random.exponential(scale=1. / self._rate, size=(n, 1))


class GammaLogPrior(pints.LogPrior):
    r"""
    Defines a gamma (log) prior with given shape parameter ``a`` and rate
    parameter ``b``, with pdf

    .. math::
        f(x|a,b)=\frac{b^a x^{a-1} e^{-bx}}{\mathrm{\Gamma}(a)}.

    where :math:`\Gamma` is the Gamma function.  A random variable :math:`X`
    distributed according to this pdf has expectation

    .. math::
        \mathrm{E}(X)=\frac{a}{b}.

    For example, to create a prior with shape parameters ``a=5`` and ``b=1``,
    use::

        p = pints.GammaLogPrior(5, 1)

    Extends :class:`LogPrior`.
    """
    def __init__(self, a, b):
        # Parse input arguments
        self._a = float(a)
        self._b = float(b)

        # Validate inputs
        if self._a <= 0:
            raise ValueError('Shape parameter a must be positive')
        if self._b <= 0:
            raise ValueError('Rate parameter b must be positive')

        # Cache constant
        self._constant = scipy.special.xlogy(self._a,
                                             self._b) - scipy.special.gammaln(
            self._a)

    def __call__(self, x):
        if x[0] < 0.0:
            return -np.inf
        else:
            return self._constant + scipy.special.xlogy(self._a - 1.,
                                                        x[0]) - self._b * x[0]

    def evaluateS1(self, x):
        """ See :meth:`LogPDF.evaluateS1()`. """
        value = self(x)

        _x = x[0]

        # Account for pathological edge
        if _x == 0.0:
            _x = np.nextafter(0.0, 1.0)

        if _x < 0.0:
            return value, np.asarray([0.])
        else:
            # Use np.divide here to better handle possible v small denominators
            return value, np.asarray([np.divide(self._a - 1., _x) - self._b])

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return self._a / self._b

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return 1

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """
        return np.random.gamma(self._a, 1. / self._b, size=(n, 1))


class GaussianLogPrior(pints.LogPrior):
    r"""
    Defines a 1-d Gaussian (log) prior with a given ``mean`` and
    standard deviation ``sd``, with pdf

    .. math::
        f(x|\text{mean},\text{sd}) = \frac{1}{\text{sd}\sqrt{2\pi}}
        \exp\left(-\frac{(x-\text{mean})^2}{2\;\text{sd}^2}\right).

    A random variable :math:`X` distributed according to this pdf has
    expectation

    .. math::
        \mathrm{E}(X)=\text{mean}.

    For example, to create a prior with mean of ``0`` and a standard deviation
    of ``1``, use::

        p = pints.GaussianLogPrior(0, 1)

    Extends :class:`LogPrior`.
    """
    def __init__(self, mean, sd):
        # Parse input arguments
        self._mean = float(mean)
        self._sd = float(sd)

        # Cache constants
        self._offset = np.log(1 / np.sqrt(2 * np.pi * self._sd ** 2))
        self._factor = 1 / (2 * self._sd ** 2)
        self._factor2 = 1 / self._sd**2

    def __call__(self, x):
        return self._offset - self._factor * (x[0] - self._mean)**2

    def cdf(self, x):
        """ See :meth:`LogPrior.cdf()`. """
        return scipy.stats.norm.cdf(x, self._mean, self._sd)

    def evaluateS1(self, x):
        """ See :meth:`LogPDF.evaluateS1()`. """
        return self(x), self._factor2 * (self._mean - np.asarray(x))

    def icdf(self, p):
        """ See :meth:`LogPrior.icdf()`. """
        return scipy.stats.norm.ppf(p, self._mean, self._sd)

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return self._mean

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return 1

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """
        return np.random.normal(self._mean, self._sd, size=(n, 1))


class HalfCauchyLogPrior(pints.LogPrior):
    r"""
    Defines a 1-d half-Cauchy (log) prior with a given ``location`` and
    ``scale``. This is a Cauchy distribution that has been truncated to lie in
    between :math:`[0,\infty]`, with pdf

    .. math::
        f(x|\text{location},\text{scale})=\begin{cases}\frac{1}{\pi\;
        \text{scale}\left(\frac{1}{\pi}\arctan\left(\frac{\text{location}}
        {\text{scale} }\right)+\frac{1}{2}\right)\left(\frac{(x-\text{location}
        )^2}{\text{scale}^2}+1\right)},&x>0\\0,&\text{otherwise.}\end{cases}

    A random variable distributed according to this pdf has undefined
    expectation.

    For example, to create a prior centered around 0 and a scale of 5, use::

        p = pints.HalfCauchyLogPrior(0, 5)

    Extends :class:`LogPrior`.

    Parameters
    ----------
    location
        The center of the distribution.
    scale
        The scale of the distribution.
    """
    def __init__(self, location, scale):
        # Test inputs
        if float(scale) <= 0:
            raise ValueError('Scale must be positive')

        self._location = location
        self._scale = scale
        self._cauchy = pints.CauchyLogPrior(location=self._location,
                                            scale=self._scale)

        # Cache constants
        self._norm_factor = -np.log(np.arctan(location / scale) / np.pi + 0.5)
        self._arctan = np.arctan(self._location / self._scale) / np.pi

    def __call__(self, x):
        if x[0] > 0:
            return self._norm_factor + self._cauchy(x)
        else:
            return -np.inf

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return np.nan

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return 1

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """

        # use inverse transform sampling
        us = np.random.uniform(0, 1, n)
        return np.array([self._inverse_cdf(u) for u in us])

    def _inverse_cdf(self, u):
        """ Inverse CDF of half-Cauchy. """
        arctan = self._arctan
        return (
            self._location + self._scale * (
                np.tan(np.pi * (-arctan + u * (0.5 + arctan)))
            ))


class InverseGammaLogPrior(pints.LogPrior):
    r"""
    Defines an inverse gamma (log) prior with given shape parameter ``a`` and
    scale parameter ``b``, with pdf

    .. math::
        f(x|a,b)=\begin{cases}\frac{b^a}{\Gamma(a)}x^{-a-1}\exp
        \left(-\frac{b}{x}\right),&x>0\\0,&\text{otherwise.}\end{cases}

    where :math:`\Gamma` is the Gamma function.  A random variable :math:`X`
    distributed according to this pdf has expectation

    .. math::
        \mathrm{E}(X)=\begin{cases}\frac{b}{a-1},&a>1\\
        \text{undefined},&\text{otherwise.}\end{cases}

    For example, to create a prior with shape parameter ``a=5`` and scale
    parameter ``b=1``, use::

        p = pints.InverseGammaLogPrior(5, 1)

    Extends :class:`LogPrior`.
    """
    def __init__(self, a, b):
        # Parse input arguments
        self._a = float(a)
        self._b = float(b)

        # Validate inputs
        if self._a <= 0:
            raise ValueError('Shape parameter a must be positive')
        if self._b <= 0:
            raise ValueError('Scale parameter b must be positive')

        # Cache constants
        self._k = self._a * np.log(self._b) - scipy.special.gammaln(self._a)
        self._ap1 = self._a + 1.

    def __call__(self, x):
        _x = float(x[0])

        if _x <= 0.0:
            return -np.inf
        else:
            return self._k - self._ap1 * np.log(_x) - np.divide(self._b, _x)

    def evaluateS1(self, x):
        """ See :meth:`LogPDF.evaluateS1()`. """
        val = self(x)

        _x = float(x[0])

        if _x < 0.0:
            return val, np.asarray([0.])
        else:
            return val, np.asarray(
                [np.divide(self._b - self._ap1 * _x, _x * _x)])

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return self._b / (self._a - 1.) if self._a > 1 else np.nan

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return 1

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """
        return scipy.stats.invgamma.rvs(a=self._a, scale=self._b, loc=0.,
                                        size=(n, 1))


class LogNormalLogPrior(pints.LogPrior):
    r"""
    Defines a log-normal (log) prior with a given ``log_mean`` and scale
    ``scale``. The ``log_mean`` parameter of a log-normal distribution is the
    mean of a normal distribution whose random samples, when exponentiated,
    yield samples from a log-normal distribution. This log-normal distribution
    has pdf

    .. math::
        f(x|\text{log_mean},\text{scale}) = \frac{1}{x\;\text{scale}
        \sqrt{2\pi}}\exp\left(-\frac{(\log x-\text{log_mean})^2}{2\;
        \text{scale}^2}\right).

    A random variable :math:`X` distributed according to this pdf has
    expectation

    .. math::
        \mathrm{E}(X)=\exp\left(\text{log_mean}+\frac{\text{scale}^2}{2}
        \right).

    For example, to create a prior with log_mean of ``0`` and a scale of ``1``,
    use::

        p = pints.LogNormalLogPrior(0, 1)

    Extends :class:`LogPrior`.
    """

    def __init__(self, log_mean, scale):
        # Parse input arguments
        self._log_mean = float(log_mean)
        self._scale = float(scale)

        if self._scale <= 0:
            raise ValueError('Scale must be positive')

        # Cache constants
        self._offset = -np.log(self._scale * np.sqrt(2. * np.pi))
        self._1on2sigsq = 1. / (2. * self._scale * self._scale)
        self._m1onsigsq = -1. / (self._scale * self._scale)
        self._sigsqmmu = self._scale * self._scale - self._log_mean

    def __call__(self, x):
        if x[0] <= 0.0:
            return -np.inf
        else:
            _lx = np.log(x[0])
            _shift = _lx - self._log_mean
            return self._offset - _lx - self._1on2sigsq * _shift * _shift

    def cdf(self, x):
        """ See :meth:`LogPrior.cdf()`. """
        return scipy.stats.lognorm.cdf(x, scale=np.exp(self._log_mean),
                                       s=self._scale)

    def evaluateS1(self, x):
        """ See :meth:`LogPDF.evaluateS1()`. """
        if x[0] < 0.0:
            return self(x), np.asarray([0.])
        else:
            _x = x[0]
            _lx = np.log(_x)
            return self(x), np.asarray(
                [self._m1onsigsq * np.divide(self._sigsqmmu + _lx, _x)])

    def icdf(self, p):
        """ See :meth:`LogPrior.icdf()`. """
        return scipy.stats.lognorm.ppf(p, scale=np.exp(self._log_mean),
                                       s=self._scale)

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return np.exp(self._log_mean + 0.5 * self._scale * self._scale)

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return 1

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """
        return scipy.stats.lognorm.rvs(scale=np.exp(self._log_mean),
                                       s=self._scale, size=(n, 1))


class MultivariateGaussianLogPrior(pints.LogPrior):
    r"""
    Defines a multivariate Gaussian (log) prior with a given ``mean`` and
    covariance matrix ``cov``, with pdf

    .. math::
        f(x|\text{mean},\text{cov}) = \frac{1}{(2\pi)^{d/2}|
        \text{cov}|^{1/2}} \exp\left(-\frac{1}{2}(x-\text{mean})'
        \text{cov}^{-1}(x-\text{mean})\right).

    A random variable :math:`X` distributed according to this pdf has
    expectation

    .. math::
        \mathrm{E}(X)=\text{mean}.

    For example, to create a prior with zero mean and identity covariance,
    use::

        p = pints.MultivariateGaussianLogPrior(
                np.array([0, 0]), np.array([[1, 0],[0, 1]]))

    Extends :class:`LogPrior`.
    """
    def __init__(self, mean, cov):
        # Check input
        mean = pints.vector(mean)
        cov = np.array(cov, copy=True)
        if cov.ndim != 2:
            raise ValueError('Given covariance must be a matrix.')
        if not (mean.shape[0] == cov.shape[0] == cov.shape[1]):
            raise ValueError('Sizes of mean and covariance do not match.')

        # Store
        self._mean = mean
        self._cov = cov
        self._n_parameters = mean.shape[0]
        self._cov_inverse = np.linalg.inv(self._cov)

        # Factors needed for pseudo-cdf calculation
        self._sigma12_sigma22_inv_l = []
        self._sigma_bar_l = []
        self._mu1 = []
        self._mu2 = []
        # note the below does not do anything for index 1 since the first
        # distribution is just a simple marginal
        for j in range(1, self._n_parameters):
                sigma = self._cov[0:(j + 1), 0:(j + 1)]
                dims = sigma.shape
                sigma11 = sigma[dims[0] - 1, dims[1] - 1]
                sigma22 = sigma[0:(dims[0] - 1), 0:(dims[0] - 1)]
                sigma12 = sigma[dims[0] - 1, 0:(dims[0] - 1)]
                sigma21 = sigma[0:(dims[0] - 1), dims[0] - 1]
                mean = self._mean[0:dims[0]]
                mu2 = mean[0:(dims[0] - 1)]
                mu1 = mean[dims[0] - 1]
                sigma12_sigma22_inv = np.matmul(sigma12,
                                                np.linalg.inv(sigma22))
                sigma_bar = np.sqrt(sigma11 - np.matmul(sigma12_sigma22_inv,
                                                        sigma21))
                if sigma_bar.size != 1:
                    raise RuntimeError("Incorrect dimensions of sigma.")
                self._sigma12_sigma22_inv_l.append(sigma12_sigma22_inv)
                self._sigma_bar_l.append(sigma_bar)
                self._mu1.append(mu1)
                self._mu2.append(mu2)

    def __call__(self, x):
        return np.log(
            scipy.stats.multivariate_normal.pdf(
                x, mean=self._mean, cov=self._cov))

    def convert_from_unit_cube(self, u):
        """
        Converts a sample ``u`` uniformly drawn from the unit cube into one
        drawn from the prior space, using
        :meth:`MultivariateGaussianLogPrior.pseudo_icdf()`.
        """
        return self.pseudo_icdf(u)

    def convert_to_unit_cube(self, x):
        """
        Converts a sample from the prior ``x`` to be drawn uniformly from the
        unit cube using :meth:`MultivariateGaussianLogPrior.pseudo_cdf()`.
        """
        return self.pseudo_cdf(x)

    def evaluateS1(self, x):
        """ See :meth:`LogPDF.evaluateS1()`. """
        return self(x), -np.matmul(self._cov_inverse, x - self._mean)

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return self._mean

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return self._n_parameters

    def pseudo_cdf(self, x):
        r"""
        Calculates a pseudo-cdf for a multivariate Gaussian as described in
        Feroz et al. (2009) ("Multnest..."). In this approach, a multivariate
        Gaussian is factorised:

        .. math::
            \pi(\theta_1,\theta_2,...,\theta_d) = \pi_1(\theta_1)
                \pi_2(\theta_2|\theta_1)...
                \pi_d(\theta_d|\theta_1, \theta_2,...,\theta_{d-1})

        The cdfs we report are then the values for each individual conditional.
        For example, for the second component, we calculate:

        .. math::
            u_2 = \int_{-\infty}^{\theta_2} \pi_2(\theta_2|\theta_1)d\theta_2

        So that we return a vector of cdfs (u_1,u_2,...,u_d).
        Note that, this function is mainly to facilitate Multinest sampling
        since the distribution (u_1,u_2,...,u_d) is uniform within the unit
        cube.
        """
        u = []
        for i in range(self._n_parameters):
            if i == 0:
                mu = self._mean[0]
                sigma = np.sqrt(self._cov[0, 0])
            else:
                sigma = self._sigma_bar_l[i - 1]
                mu = self._mu1[i - 1] + np.matmul(
                    self._sigma12_sigma22_inv_l[i - 1],
                    (x[0:i] - self._mu2[i - 1]))
            u.append(scipy.stats.norm.cdf(x[i], mu, sigma))
        return u

    def pseudo_icdf(self, u):
        r"""
        Calculates a pseudo-icdf for a multivariate Gaussian as described in
        Feroz et al. (2009) ("Multnest..."). In this approach, a multivariate
        Gaussian is factorised:

        .. math::
            \pi(\theta_1,\theta_2,...,\theta_d) = \pi_1(\theta_1)
                \pi_2(\theta_2|\theta_1)...
                \pi_d(\theta_d|\theta_1, \theta_2,...,\theta_{d-1})

        The icdfs we report are then the values for each individual
        conditional. For example, for the second component, we calculate the
        theta_2 value that satisfies:

        .. math::
            u_2 = \int_{-\infty}^{\theta_2} \pi_2(\theta_2|\theta_1)d\theta_2

        So that we return a vector of icdfs (theta_1,theta_2,...,theta_d)
        Note that, this function is mainly to facilitate Multinest sampling
        since the distribution (u_1,u_2,...,u_d) is uniform within the unit
        cube.
        """
        theta = []
        for i in range(self._n_parameters):
            if i == 0:
                mu = self._mean[0]
                sigma = np.sqrt(self._cov[0, 0])
            else:
                sigma = self._sigma_bar_l[i - 1]
                mu = self._mu1[i - 1] + np.matmul(
                    self._sigma12_sigma22_inv_l[i - 1],
                    (np.array(theta[0:i]) - self._mu2[i - 1]))
            theta.append(scipy.stats.norm.ppf(u[i], mu, sigma))
        return theta

    def sample(self, n=1):
        """ See :meth:`LogPrior.call()`. """
        # Note: size=n returns shape (n, d)
        return np.random.multivariate_normal(
            self._mean, self._cov, size=n)


class NormalLogPrior(GaussianLogPrior):
    r""" Deprecated alias of :class:`GaussianLogPrior`. """

    def __init__(self, mean, standard_deviation):
        # Deprecated on 2019-02-06
        import logging
        logging.basicConfig()
        log = logging.getLogger(__name__)
        log.warning(
            'The class `pints.NormalLogPrior` is deprecated.'
            ' Please use `pints.GaussianLogPrior` instead.')
        super(NormalLogPrior, self).__init__(mean, standard_deviation)


class StudentTLogPrior(pints.LogPrior):
    r"""
    Defines a 1-d Student-t (log) prior with a given ``location``,
    degrees of freedom ``df``,  and ``scale`` with pdf

    .. math::
        f(x|\text{location},\text{scale},\text{df})=\frac{\left(\frac{
        \text{df}}{\text{df}+\frac{(x-\text{location})^2}{\text{scale}^2}}
        \right)^{\frac{\text{df}+1}{2}}}{\sqrt{\text{df}}\;\text{scale}
        \;\mathrm{B}\left(\frac{\text{df} }{2},\frac{1}{2}\right)}.

    where :math:`\mathrm{B}` is the Beta function. A random variable :math:`X`
    distributed according to this pdf has expectation

    .. math::
        \mathrm{E}(X)=\begin{cases}\text{location},&\text{df}>1\\\
        \text{undefined},&\text{otherwise.}\end{cases}

    For example, to create a prior centered around 0 with 3 degrees of freedom
    and a scale of 1, use::

        p = pints.StudentTLogPrior(0, 3, 1)

    Extends :class:`LogPrior`.

    Parameters
    ----------
    location
        The center of the distribution.
    df : int
        The number of degrees of freedom of the distribution.
    scale
        The scale of the distribution.
    """
    def __init__(self, location, df, scale):
        # Test inputs
        if float(df) <= 0:
            raise ValueError('Degrees of freedom must be positive')
        if float(scale) <= 0:
            raise ValueError('Scale must be positive')

        # Parse input arguments
        self._df = float(df)
        self._location = float(location)
        self._scale = float(scale)

        # Cache constants
        self._log_df = np.log(self._df)

        self._1_sig_sq = 1. / (self._scale * self._scale)

        self._first = 0.5 * (1.0 + self._df)

        self._samp_const = scipy.special.xlogy(-0.5, self._df) - np.log(
            self._scale) - scipy.special.betaln(0.5 * self._df, 0.5)

        self._deriv_const = (-1. - self._df) * self._1_sig_sq

    def __call__(self, x):
        return self._samp_const + self._first * (self._log_df - np.log(
            self._df + self._1_sig_sq * (x[0] - self._location) ** 2))

    def evaluateS1(self, x):
        """ See :meth:`LogPDF.evaluateS1()`. """
        offset = x[0] - self._location
        return self(x), np.asarray([offset * self._deriv_const / (
            self._df + offset * offset * self._1_sig_sq)])

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        return self._location if self._df > 1. else np.nan

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return 1

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """
        return scipy.stats.t.rvs(df=self._df, loc=self._location,
                                 scale=self._scale, size=(n, 1))


class UniformLogPrior(pints.LogPrior):
    r"""
    Defines a uniform prior over a given range.

    The range includes the lower, but not the upper boundaries, so that any
    point ``x`` with a non-zero prior must have ``lower <= x < upper``.

    In 1D this has pdf

    .. math::
        f(x|\text{lower},\text{upper})=\begin{cases}0,&\text{if }x\not\in
        [\text{lower},\text{upper})\\\frac{1}{\text{upper}-\text{lower}}
        ,&\text{if }x\in[\text{lower},\text{upper})\end{cases}.

    A random variable :math:`X` distributed according to this pdf has
    expectation

    .. math::
        \mathrm{E}(X)=\frac{1}{2}(\text{lower}+\text{upper}).

    For example, to create a prior with :math:`x\in[0,4]`, :math:`y\in[1,5]`,
    and :math:`z\in[2,6]` use either::

        p = pints.UniformLogPrior([0, 1, 2], [4, 5, 6])

    or::

        p = pints.UniformLogPrior(RectangularBoundaries([0, 1, 2], [4, 5, 6]))

    Extends :class:`LogPrior`.
    """
    def __init__(self, lower_or_boundaries, upper=None):
        # Parse input arguments
        if upper is None:
            if not isinstance(lower_or_boundaries, pints.Boundaries):
                raise ValueError(
                    'UniformLogPrior requires a lower and an upper bound, or a'
                    ' single Boundaries object.')
            self._boundaries = lower_or_boundaries
        else:
            self._boundaries = pints.RectangularBoundaries(
                lower_or_boundaries, upper)

        # Cache dimension
        self._n_parameters = self._boundaries.n_parameters()

        # Maximum output value
        # Use normalised value (1/area) for rectangular boundaries,
        # otherwise just use 1.
        if isinstance(self._boundaries, pints.RectangularBoundaries):
            self._value = -np.log(np.product(self._boundaries.range()))
        else:
            self._value = 1

    def __call__(self, x):
        return self._value if self._boundaries.check(x) else -np.inf

    def cdf(self, xs):
        """ See :meth:`LogPrior.cdf()`. """
        if not isinstance(xs, list):
            xs = [xs]
        cdfs = []
        for i, x in enumerate(xs):
            if x > self._boundaries.lower()[i] and (
                    x < self._boundaries.upper()[i]):
                cdfs.append((-self._boundaries.lower()[i] + x) /
                            (-self._boundaries.lower()[i] +
                             self._boundaries.upper()[i]))
            elif x >= self._boundaries.upper()[i]:
                cdfs.append(1.0)
            else:
                cdfs.append(0.0)
        if len(cdfs) == 1:
            return cdfs[0]
        else:
            return cdfs

    def icdf(self, ps):
        """ See :meth:`LogPrior.icdf()`. """
        if not isinstance(ps, list):
            ps = [ps]
        icdfs = []
        for i, p in enumerate(ps):
            if p > 0 and p < 1:
                icdfs.append(
                    self._boundaries.lower()[i] * (1 - p) +
                    self._boundaries.upper()[i] * p)
            elif p <= 0:
                icdfs.append(self._boundaries.lower()[i])
            else:
                icdfs.append(self._boundaries.upper()[i])
        if len(icdfs) == 1:
            return icdfs[0]
        else:
            return icdfs

    def evaluateS1(self, x):
        """ See :meth:`LogPrior.evaluateS1()`. """
        # Ignoring points on the boundaries (i.e. on the surface of the
        # hypercube), because it's very unlikely and won't help the search
        # much...
        return self(x), np.zeros(self._n_parameters)

    def mean(self):
        """ See :meth:`LogPrior.mean()`. """
        if isinstance(self._boundaries, pints.RectangularBoundaries):
            return 0.5 * (self._boundaries.lower() + self._boundaries.upper())
        else:
            raise NotImplementedError

    def n_parameters(self):
        """ See :meth:`LogPrior.n_parameters()`. """
        return self._n_parameters

    def sample(self, n=1):
        """ See :meth:`LogPrior.sample()`. """
        return self._boundaries.sample(n)
