import numpy as np
from scipy.special import gammaln, psi

from pyhawkes.deps.pybasicbayes.distributions import GibbsSampling, MeanField, MeanFieldSVI
from pyhawkes.internals.distributions import Dirichlet

class DirichletImpulseResponses(GibbsSampling, MeanField, MeanFieldSVI):
    """
    Encapsulates the impulse response vector distribution. In the
    discrete time Hawkes model this is a set of Dirichlet-distributed
    vectors of length B for each pair of processes, k and k', which
    we denote $\bbeta^{(k,k')}. This class contains all K^2 vectors.
    """
    def __init__(self, K, B, gamma=None):
        """
        Initialize a set of Dirichlet weight vectors.
        :param K:     The number of processes in the model.
        :param B:     The number of basis functions in the model.
        :param gamma: The Dirichlet prior parameter. If none it will be set
                      to a symmetric prior with parameter 1.
        """
        # assert isinstance(model, DiscreteTimeNetworkHawkesModel), \
        #        "model must be a DiscreteTimeNetworkHawkesModel"
        # self.model = model
        self.K = K
        self.B = B

        if gamma is not None:
            assert np.isscalar(gamma) or \
                   (isinstance(gamma, np.ndarray) and
                    gamma.shape == (B,)), \
                "gamma must be a scalar or a length B vector"

            if np.isscalar(gamma):
                self.gamma = gamma * np.ones(B)
            else:
                self.gamma = gamma
        else:
            self.gamma = np.ones(self.B)

        # Initialize with a draw from the prior
        self.g = np.empty((self.K, self.K, self.B))
        self.resample()

        # Initialize mean field parameters
        self.mf_gamma = self.gamma[None, None, :] * np.ones((self.K, self.K, self.B))

    def rvs(self, size=[]):
        """
        Sample random variables from the Dirichlet impulse response distribution.
        :param size:
        :return:
        """
        pass

    def log_likelihood(self, x):
        '''
        log likelihood (either log probability mass function or log probability
        density function) of x, which has the same type as the output of rvs()
        '''
        assert isinstance(x, np.ndarray) and x.shape == (self.K,self.K,self.B), \
            "x must be a KxKxB array of impulse responses"

        gamma = self.gamma
        # Compute the normalization constant
        Z = gammaln(gamma).sum() - gammaln(gamma.sum())
        # Add the likelihood of x
        return self.K**2 * Z + ((gamma-1.0)[None,None,:] * np.log(x)).sum()

    def log_probability(self):
        return self.log_likelihood(self.g)

    def _get_suff_statistics(self, data):
        """
        Compute the sufficient statistics from the data set.
        :param data: a TxK array of event counts assigned to the background process
        :return:
        """
        # The only sufficient statistic is the KxKxB array of event counts assigned
        # to each of the basis functions
        if data is not None:
            ss = data.sum(axis=0)
        else:
            ss = np.zeros((self.K, self.K, self.B))

        return ss

    def resample(self, data=None):
        """
        Resample the
        :param data: a TxKxKxB array of parents. T time bins, K processes,
                     K parent processes, and B bases for each parent process.
        """
        assert data is None or \
               (isinstance(data, np.ndarray) and
                data.ndim == 4 and
                data.shape[1] == data.shape[2] == self.K
                and data.shape[3] == self.B), \
            "Data must be a TxKxKxB array of parents"


        ss = self._get_suff_statistics(data)
        for k1 in xrange(self.K):
            for k2 in xrange(self.K):
                alpha_post = self.gamma + ss[k1, k2, :]
                self.g[k1,k2,:] = np.random.dirichlet(alpha_post)

    def expected_g(self):
        # \sum_{b} \gamma_b
        trm2 = self.mf_gamma.sum(axis=2)
        E_g = self.mf_gamma / trm2[:,:,None]
        return E_g

    def expected_log_g(self):
        E_lng = np.zeros_like(self.mf_gamma)

        # \psi(\sum_{b} \gamma_b)
        trm2 = psi(self.mf_gamma.sum(axis=2))
        for b in xrange(self.B):
            E_lng[:,:,b] = psi(self.mf_gamma[:,:,b]) - trm2

        return E_lng

    def mf_update_gamma(self, EZ, minibatchfrac=1.0, stepsize=1.0):
        """
        Update gamma given E[Z]
        :return:
        """
        gamma_hat = self.gamma + EZ.sum(axis=0) / minibatchfrac
        self.mf_gamma = (1.0 - stepsize) * self.mf_gamma + stepsize * gamma_hat

    def expected_log_likelihood(self,x):
        pass

    def meanfieldupdate(self, EZ):
        self.mf_update_gamma(EZ)

    def meanfield_sgdstep(self, EZ, minibatchfrac, stepsize):
        self.mf_update_gamma(EZ, minibatchfrac=minibatchfrac, stepsize=stepsize)

    def get_vlb(self):
        """
        Variational lower bound for \lambda_k^0
        E[LN p(g | \gamma)] -
        E[LN q(g | \tilde{\gamma})]
        :return:
        """
        vlb = 0

        # First term
        # E[LN p(g | \gamma)]
        E_ln_g = self.expected_log_g()
        vlb += Dirichlet(self.gamma[None, None, :]).negentropy(E_ln_g=E_ln_g).sum()

        # Second term
        # E[LN q(g | \tilde{gamma})]
        vlb -= Dirichlet(self.mf_gamma).negentropy().sum()

        return vlb

    def resample_from_mf(self):
        """
        Resample from the mean field distribution
        :return:
        """
        self.g = np.zeros((self.K, self.K, self.B))
        for k1 in xrange(self.K):
            for k2 in xrange(self.K):
                self.g[k1,k2,:] = np.random.dirichlet(self.mf_gamma[k1,k2,:])


class SBMDirichletImpulseResponses(GibbsSampling):
    """
    A impulse response vector model with a set of Dirichlet-distributed
    vectors of length B for each pair of blocks, c and c', which
    we denote $\bbeta^{(c,c')}. This class contains all C^2 vectors.
    """
    def __init__(self, C, K, B, gamma=None):
        """
        Initialize a set of Dirichlet weight vectors.
        :param K:     The number of processes in the model.
        :param B:     The number of basis functions in the model.
        :param gamma: The Dirichlet prior parameter. If none it will be set
                      to a symmetric prior with parameter 1.
        """
        self.C = C
        self.K = K
        self.B = B

        if gamma is not None:
            assert np.isscalar(gamma) or \
                   (isinstance(gamma, np.ndarray) and
                    gamma.shape == (B,)), \
                "gamma must be a scalar or a length B vector"

            if np.isscalar(gamma):
                self.gamma = gamma * np.ones(B)
            else:
                self.gamma = gamma
        else:
            self.gamma = np.ones(self.B)

        # Initialize with a draw from the prior
        self.blockg = np.empty((self.C, self.C, self.B))
        self.resample()

        # Initialize mean field parameters
        self.mf_gamma = self.gamma[None, None, :] * np.ones((self.C, self.C, self.B))

    def rvs(self, size=[]):
        """
        Sample random variables from the Dirichlet impulse response distribution.
        :param size:
        :return:
        """
        raise NotImplementedError()

    def log_likelihood(self, x):
        '''
        log likelihood (either log probability mass function or log probability
        density function) of x, which has the same type as the output of rvs()
        '''
        raise NotImplementedError()
        assert isinstance(x, np.ndarray) and x.shape == (self.K,self.K,self.B), \
            "x must be a KxKxB array of impulse responses"

        gamma = self.gamma
        # Compute the normalization constant
        Z = gammaln(gamma).sum() - gammaln(gamma.sum())
        # Add the likelihood of x
        return self.K**2 * Z + ((gamma-1.0)[None,None,:] * np.log(x)).sum()

    def log_probability(self):
        return self.log_likelihood(self.g)

    def _get_suff_statistics(self, data):
        """
        Compute the sufficient statistics from the data set.
        :param data: a TxK array of event counts assigned to the background process
        :return:
        """
        raise NotImplementedError()
        # The only sufficient statistic is the KxKxB array of event counts assigned
        # to each of the basis functions
        if data is not None:
            ss = data.sum(axis=0)
        else:
            ss = np.zeros((self.K, self.K, self.B))

        return ss

    def resample(self, data=None):
        """
        Resample the
        :param data: a TxKxKxB array of parents. T time bins, K processes,
                     K parent processes, and B bases for each parent process.
        """
        raise NotImplementedError()
        assert data is None or \
               (isinstance(data, np.ndarray) and
                data.ndim == 4 and
                data.shape[1] == data.shape[2] == self.K
                and data.shape[3] == self.B), \
            "Data must be a TxKxKxB array of parents"


        ss = self._get_suff_statistics(data)
        for k1 in xrange(self.K):
            for k2 in xrange(self.K):
                alpha_post = self.gamma + ss[k1, k2, :]
                self.g[k1,k2,:] = np.random.dirichlet(alpha_post)

    def expected_g(self):
        """
        Compute the expected impulse response vector wrt c and mf_gamma
        :return:
        """
        raise NotImplementedError()
        # \sum_{b} \gamma_b
        trm2 = self.mf_gamma.sum(axis=2)
        E_g = self.mf_gamma / trm2[:,:,None]
        return E_g

    def expected_log_g(self):
        """
        Compute the expected log impulse response vector wrt c and mf_gamma
        :return:
        """
        raise NotImplementedError()
        E_lng = np.zeros_like(self.mf_gamma)

        # \psi(\sum_{b} \gamma_b)
        trm2 = psi(self.mf_gamma.sum(axis=2))
        for b in xrange(self.B):
            E_lng[:,:,b] = psi(self.mf_gamma[:,:,b]) - trm2

        return E_lng

    def mf_update_gamma(self, EZ):
        """
        Update gamma given E[Z]
        :return:
        """
        raise NotImplementedError()
        self.mf_gamma = self.gamma + EZ.sum(axis=0)

    def expected_log_likelihood(self,x):
        raise NotImplementedError()
        pass

    def meanfieldupdate(self, EZ):
        raise NotImplementedError()
        self.mf_update_gamma(EZ)

    def get_vlb(self):
        """
        Variational lower bound for \lambda_k^0
        E[LN p(g | \gamma)] -
        E[LN q(g | \tilde{\gamma})]
        :return:
        """
        raise NotImplementedError()
        vlb = 0

        # First term
        # E[LN p(g | \gamma)]
        E_ln_g = self.expected_log_g()
        vlb += Dirichlet(self.gamma[None, None, :]).negentropy(E_ln_g=E_ln_g).sum()

        # Second term
        # E[LN q(g | \tilde{gamma})]
        vlb -= Dirichlet(self.mf_gamma).negentropy().sum()

        return vlb

    def resample_from_mf(self):
        """
        Resample from the mean field distribution
        :return:
        """
        raise NotImplementedError()
        self.g = np.zeros((self.K, self.K, self.B))
        for k1 in xrange(self.K):
            for k2 in xrange(self.K):
                self.g[k1,k2,:] = np.random.dirichlet(self.mf_gamma[k1,k2,:])