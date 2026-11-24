"""Standalone Chasapis PbSe forward calculation; not production SeeBand physics."""

from functools import lru_cache

import numpy as np
from scipy.constants import Boltzmann as KB_J
from scipy.constants import electron_mass as M0
from scipy.constants import elementary_charge as E
from scipy.constants import hbar
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import expit

KB_EV = KB_J / E
PUBLISHED_DENSITIES_CM3 = {"0.01": 1.8e20, "0.02": 4.7e20, "0.03": 7.6e20}


def material_parameters(temperature_k):
    """Table I total DOS masses (already include valley multiplicities 4,12)."""
    t = np.asarray(temperature_k, dtype=float)
    if np.any(~np.isfinite(t)) or np.any(t <= 0):
        raise ValueError("temperature_k must be finite and positive")
    return {
        "gap_ev": 0.17 + 3e-4 * t,
        "offset_ev": 0.32 - 2.2e-4 * t,
        "mass_l_m0": 0.18 + 3e-4 * t,
        "mass_sigma_m0": np.full_like(t, 2.5),
    }


@lru_cache(maxsize=32768)
def generalized(eta, alpha, n, m, k, relative_tolerance=2e-10):
    """Eq4 integral, scaled by exp(-min(eta,0)); avoids minority underflow.

    Tail truncated 55 kBT from the Fermi window; tail error is much smaller
    than the requested quadrature tolerance in this paper's 10--900 K range.
    The density integral uses a derivative Fermi measure as in Eq6.
    """
    low, high = max(0.0, eta - 55), max(55.0, eta + 55)

    def integrand(x):
        y = x - eta
        derivative = np.exp(-x) / (1 + np.exp(-y)) ** 2 if eta < 0 else expit(y) * expit(-y)
        return (
            derivative * x**n * (x + alpha * x * x) ** m * ((1 + 2 * alpha * x) ** 2 + 2) ** (k / 2)
        )

    return quad(integrand, low, high, epsabs=1e-12, epsrel=relative_tolerance, limit=200)[0]


def band_observables(
    eta, alpha, temperature_k, mass_dos_m0, anisotropy, *, relative_tolerance=2e-10
):
    """Eqs4--9; positive holes; S in uV/K, density cm^-3, RH cm^3/C.

    g_paper is the generalized transport integral (F0/3 at alpha=0).
    Normalized integrals are used for ratios before restoring exp(min(eta,0)).
    """

    def integral(n, m, k):
        return generalized(float(eta), float(alpha), n, m, k, relative_tolerance)

    density_i, j0, j1, hall_i = (
        integral(0, 1.5, 0),
        integral(0, 1, -2),
        integral(1, 1, -2),
        integral(0, 0.5, -4),
    )
    density_cm3 = (
        (2 * mass_dos_m0 * M0 * KB_J * temperature_k) ** 1.5
        / (3 * np.pi**2 * hbar**3)
        * density_i
        * np.exp(min(eta, 0))
        / 1e6
    )
    hall_factor = (
        3 * anisotropy * (anisotropy + 2) / (2 * anisotropy + 1) ** 2 * hall_i * density_i / j0**2
    )
    return {
        "density_cm3": density_cm3,
        "s_uv_k": KB_EV * 1e6 * (j1 / j0 - eta),
        "rh_cm3_c": hall_factor / (E * density_cm3),
        "hall_factor": hall_factor,
        "g_paper": j0 * np.exp(min(eta, 0)),
    }


def forward(
    temperature_k,
    total_holes_cm3,
    *,
    freeze_structure_at_k=None,
    anisotropy_l=1.75,
    relative_tolerance=2e-10,
):
    """Fixed Eq18 neutrality using Table I for every sample, including x=.03.

    temperature_k may be scalar or 1D; returned columns are always 1D arrays.
    The ambiguous x=.03 mass law on paper p25 is deliberately not inferred.
    freeze_structure_at_k holds gap, offset and masses at that temperature;
    actual T still sets occupations and alpha. anisotropy_l=1 matches the
    isotropic TDD Hall convention; 1.75 retains the paper's anisotropy.
    """
    t = np.atleast_1d(np.asarray(temperature_k, dtype=float))
    if t.ndim != 1 or not np.isfinite(total_holes_cm3) or total_holes_cm3 <= 0:
        raise ValueError("require 1D temperatures and a finite positive total_holes_cm3")
    if not np.isfinite(anisotropy_l) or anisotropy_l <= 0:
        raise ValueError("anisotropy_l must be finite and positive")
    material_parameters(t)  # Validate actual temperatures even for frozen structure.
    structure_t = t if freeze_structure_at_k is None else np.full_like(t, freeze_structure_at_k)
    result = {"temperature_k": t.copy(), **material_parameters(structure_t)}
    rows = []
    for i, temp in enumerate(t):
        alpha = KB_EV * temp / result["gap_ev"][i]
        delta = result["offset_ev"][i] / (KB_EV * temp)
        mass_l = result["mass_l_m0"][i]

        def bands(eta_l, alpha=alpha, temp=temp, mass_l=mass_l, delta=delta):
            return (
                band_observables(
                    eta_l, alpha, temp, mass_l, anisotropy_l, relative_tolerance=relative_tolerance
                ),
                band_observables(
                    eta_l - delta, 0.0, temp, 2.5, 1.0, relative_tolerance=relative_tolerance
                ),
            )

        def neutrality(eta_l):
            left, right = bands(eta_l)
            return (left["density_cm3"] + right["density_cm3"]) / total_holes_cm3 - 1

        lower, upper = -100.0, max(100.0, delta + 100)
        while neutrality(upper) < 0:
            upper *= 2
        eta = brentq(neutrality, lower, upper, xtol=1e-11, rtol=1e-13)
        left, right = bands(eta)
        if abs(neutrality(eta)) > 2e-10:
            raise ArithmeticError("fixed-neutrality residual exceeds 2e-10")
        rows.append(
            {
                "eta_l": eta,
                "eta_sigma": eta - delta,
                "p_l_cm3": left["density_cm3"],
                "p_sigma_cm3": right["density_cm3"],
                "s_l_uv_k": left["s_uv_k"],
                "s_sigma_uv_k": right["s_uv_k"],
                "rh_l_cm3_c": left["rh_cm3_c"],
                "rh_sigma_cm3_c": right["rh_cm3_c"],
                "hall_factor_l": left["hall_factor"],
                "hall_factor_sigma": right["hall_factor"],
                "g_l": left["g_paper"],
                "g_sigma": 3 * right["g_paper"],
            }
        )
    if rows:
        result.update({key: np.array([row[key] for row in rows]) for key in rows[0]})
        result["g_l_over_g_sigma"] = result["g_l"] / result["g_sigma"]
    return result


def combine(bands, f0):
    """Paper Eqs12--14: f=sigma_L/sigma_Sigma=3*f0*g_L/g_Sigma.

    SeeBand Sigma/L prefactor w2=1/(3*f0), since g_Sigma=F0 here.
    f0 is dimensionless and must be nonnegative; accept an array over T.
    """
    f0 = np.asarray(f0, dtype=float)
    if np.any(~np.isfinite(f0)) or np.any(f0 < 0):
        raise ValueError("f0 must be finite and nonnegative")
    ratio = 3 * f0 * bands["g_l_over_g_sigma"]
    weight_l, weight_sigma = ratio / (1 + ratio), 1 / (1 + ratio)
    return {
        "s_uv_k": weight_l * bands["s_l_uv_k"] + weight_sigma * bands["s_sigma_uv_k"],
        "rh_cm3_c": weight_l**2 * bands["rh_l_cm3_c"] + weight_sigma**2 * bands["rh_sigma_cm3_c"],
        "conductivity_l_over_sigma": ratio,
    }


def self_check():
    """Independent limits and the fixed-neutrality contract at the public seam."""
    import numpy as np

    band = band_observables(-30.0, 0.0, 300.0, 2.5, 1.0)
    assert np.isclose(band["hall_factor"], 3 * np.pi / 8, rtol=2e-7)
    assert np.isclose(band["s_uv_k"], KB_EV * 1e6 * 32, rtol=2e-7)
    assert np.isclose(band["g_paper"] / np.exp(-30), 1 / 3, rtol=2e-7)
    # Independent density expression: integrate occupied DOS, not df/dx.
    eta, alpha = 4.0, 0.1
    direct = quad(
        lambda x: 1.5 * np.sqrt(x + alpha * x * x) * (1 + 2 * alpha * x) * expit(eta - x),
        0,
        100,
        epsabs=1e-10,
    )[0]
    assert np.isclose(generalized(eta, alpha, 0, 1.5, 0), direct, rtol=2e-10)
    for density in PUBLISHED_DENSITIES_CM3.values():
        bands = forward([10, 300, 650, 900], density)
        assert np.allclose(bands["p_l_cm3"] + bands["p_sigma_cm3"], density, rtol=2e-10)
        assert np.all(bands["s_l_uv_k"] > 0) and np.all(bands["s_sigma_uv_k"] > 0)
        assert np.all(bands["rh_l_cm3_c"] > 0) and np.all(bands["rh_sigma_cm3_c"] > 0)
        refined = forward([900, 10, 650, 300], density, relative_tolerance=2e-12)
        for key in (
            "p_l_cm3",
            "p_sigma_cm3",
            "s_l_uv_k",
            "s_sigma_uv_k",
            "rh_l_cm3_c",
            "rh_sigma_cm3_c",
            "g_l",
            "g_sigma",
        ):
            assert np.allclose(bands[key], refined[key][[1, 3, 2, 0]], rtol=2e-8, atol=0)
        frozen = forward([300, 650, 900], density, freeze_structure_at_k=300, anisotropy_l=1)
        assert np.all(frozen["gap_ev"] == 0.26) and np.all(frozen["mass_l_m0"] == 0.27)
        assert np.isclose(frozen["s_l_uv_k"][0], bands["s_l_uv_k"][1])
        assert np.isclose(
            frozen["rh_l_cm3_c"][0] * (3 * 1.75 * 3.75 / 4.5**2), bands["rh_l_cm3_c"][1]
        )
        mix = combine(bands, 2.0)
        assert np.allclose(mix["conductivity_l_over_sigma"], 6 * bands["g_l_over_g_sigma"])
        assert np.all(mix["s_uv_k"] >= bands["s_l_uv_k"])
        assert np.all(mix["s_uv_k"] <= bands["s_sigma_uv_k"])
    print("PASS: PbSe limits, neutrality, prefactors and refinement")  # noqa: T201


if __name__ == "__main__":
    self_check()
