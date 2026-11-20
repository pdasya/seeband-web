"""Scalar unnormalized Fermi–Dirac integrals used by SeeBand transport."""

from functools import lru_cache
from math import exp, gamma, log1p

import numpy as np
from scipy.special import expit, roots_jacobi, roots_legendre

_WINDOW = 48.0
_EDGE = 8.0

# Short Gauss–Legendre panels resolve the Fermi window on a fixed grid.
_NODES, _WEIGHTS = roots_legendre(64)
_UNIT_X = ((np.arange(4)[:, None] + (_NODES + 1.0) / 2.0) / 4.0).ravel()
_UNIT_W = np.tile(_WEIGHTS / 8.0, 4)
_WINDOW_MIDPOINTS = np.array([-30.0, -6.0, 6.0, 30.0])[:, None]
_WINDOW_HALF_WIDTHS = np.array([18.0, 6.0, 6.0, 18.0])[:, None]
_WINDOW_X = (_WINDOW_MIDPOINTS + _WINDOW_HALF_WIDTHS * _NODES).ravel()
_WINDOW_W = (_WINDOW_HALF_WIDTHS * _WEIGHTS).ravel() * expit(_WINDOW_X) * expit(-_WINDOW_X)


@lru_cache(maxsize=16)
def _edge_rule(order: float) -> tuple[np.ndarray, np.ndarray]:
    # Integrate by parts, so the endpoint factor is x**(order + 1).
    # Gauss–Jacobi absorbs that factor even for fractional orders.
    nodes, weights = roots_jacobi(24, 0.0, order + 1.0)
    half_width = _EDGE / 2.0
    return half_width * (nodes + 1.0), half_width ** (order + 2.0) * weights


@lru_cache(maxsize=16)
def _negative_rule(order: float) -> tuple[np.ndarray, np.ndarray]:
    edge_x, edge_w = _edge_rule(order)
    width = _WINDOW - _EDGE
    x = _EDGE + width * _UNIT_X
    boltzmann = np.exp(-np.concatenate((edge_x, x)))
    weights = np.concatenate((edge_w, width * _UNIT_W * x ** (order + 1.0)))
    return boltzmann, weights * boltzmann / (order + 1.0)


def scaled_fermi_integral(order: float, reduced_mu: float) -> float:
    """Return F_order(eta) times exp(-min(eta, 0)), for -1 < order <= 4."""
    if not -1.0 < order <= 4.0:
        raise ValueError("Fermi integral order must be in (-1, 4]")
    eta = reduced_mu
    if eta <= -38.0:
        # Here the first omitted fugacity term is below float precision.
        return gamma(order + 1.0)
    if order == 0.0:
        fugacity = exp(-abs(eta))
        return log1p(fugacity) / fugacity if eta < 0.0 else eta + log1p(fugacity)
    if eta < 0.0:
        # The derivative of the Fermi occupation divided by exp(eta) is
        # exp(-x) / (1 + exp(eta) * exp(-x))**2.
        boltzmann, weights = _negative_rule(order)
        return float(np.dot(weights, (1.0 + exp(eta) * boltzmann) ** -2))
    if eta >= _WINDOW:
        # Integrate in x - eta to keep the narrow window resolved at large eta.
        return float(np.dot(_WINDOW_W, (eta + _WINDOW_X) ** (order + 1.0)) / (order + 1.0))

    edge_x, edge_w = _edge_rule(order)
    width = eta + _WINDOW - _EDGE
    x = _EDGE + width * _UNIT_X
    edge = edge_x - eta
    centered = x - eta
    edge_moment = np.dot(edge_w, expit(edge) * expit(-edge))
    moment = np.dot(_UNIT_W, x ** (order + 1.0) * expit(centered) * expit(-centered))
    return float((edge_moment + width * moment) / (order + 1.0))


def fermi_integral(order: float, reduced_mu: float) -> float:
    """Integrate x**order / (1 + exp(x - eta)) over x >= 0 for -1 < order <= 4."""
    eta = reduced_mu
    if order == 0.0:
        return max(eta, 0.0) + log1p(exp(-abs(eta)))
    scaled = scaled_fermi_integral(order, eta)
    if eta >= 0.0:
        return scaled
    if eta < -700.0:
        # Keep exp(eta) normal until the final multiply in the subnormal range.
        return exp(eta + 512.0) * (scaled * exp(-512.0))
    return exp(eta) * scaled
