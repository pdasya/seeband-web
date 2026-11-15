"""Reproduce example 03's P11 outer-loop fixed point without the production fitter.

Run from the checkout with PYTHONPATH=packages/seeband_core/src:
    .venv/bin/python packages/seeband_core/scripts/check_p11_fixed_point.py

Only historical desktop inputs are read; no P11 generated results are used.
The pointwise Seebeck objective is assembled from shared charge/transport kernels.
Independence covers stage orchestration and settlement, not the shared physics.
The objectives, bounds, scales and solver budgets match the original stages.
C and D start at 2 and 0.5 in public units (600 K and 150 K internally), N = 1.
Hall is a subsequent stage and does not feed back into these seven parameters.
"""

# Diagnostic CLI intentionally prints only public fit parameters and residual summaries.
# ruff: noqa: T201

import json
import platform
import warnings
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import curve_fit
from seeband_core import math_module as kernels

ROOT = Path(__file__).resolve().parents[1]


def check_fixed_point(hall: bool) -> None:
    document = json.loads((ROOT / "tests/fixtures/golden/03_AWI32_SI.json").read_text())
    mode = "dpb_s_rho_rh" if hall else "dpb_s_rho"
    run = next(r for r in document["runs"] if r["mode"] == mode and r["scattering"] == "acPhDis")
    args = run["calls"][0]["args"]
    data_count = 6 if hall else 4
    temp_s, measured_s, temp_rho, measured_rho = map(np.asarray, args[:4])
    bands = np.array(args[data_count], dtype=float)
    bounds_s = np.asarray(args[data_count + 1], dtype=float)
    scattering = np.array(args[data_count + 2][:4], dtype=float)
    scattering[2:] = [600.0, 150.0]
    bounds_rho = np.asarray(args[data_count + 3], dtype=float)[:, :4]
    bounds_rho[:, 2:] *= 300.0
    assert args[data_count + (6 if hall else 4)] == 1.0

    def seebeck(temperature_k, mass, gap, fermi_energy):
        potentials = kernels.dpb_chemPot_vs_temp(temperature_k, gap, mass, fermi_energy, 1.0)
        values = []
        for temp, mu in zip(temperature_k, potentials, strict=True):
            sigma1 = kernels.sigma_general(mu, -1, 1, -1, temp)
            sigma2 = kernels.sigma_general(mu - gap, np.sign(mass), 1, -1, temp)
            onsager1 = kernels.onsi_general(mu, -1, 1, -1, temp)
            onsager2 = kernels.onsi_general(mu - gap, np.sign(mass), 1, -1, temp)
            weight = scattering[1] * (scattering[2] + temp) / (scattering[3] + temp) / mass
            values.append(1e6 * (onsager1 + weight * onsager2) / (sigma1 + weight * sigma2))
        return np.array(values)

    history = []
    first_stop = None
    for cycle in range(1, 13):
        previous = np.r_[bands, scattering]
        bands, _ = curve_fit(
            seebeck, temp_s, measured_s * 1e6, p0=bands, bounds=bounds_s, maxfev=1000
        )
        fermi1, fermi2 = kernels.dpb_fermiInt_vs_temp(
            s=0, T=temp_rho, mass=bands[0], gap=bands[1], fermi_energy=bands[2], degen=1.0
        )

        def resistivity(temperature_k, a, b, c, d, *, f1=fermi1, f2=fermi2, mass=bands[0]):
            return kernels.dpb_rho_vs_temp_acPh_dis(
                temperature_k, f1, f2, a, b, c, d, mass, scal_fac=1e8
            )

        scattering, _ = curve_fit(
            resistivity,
            temp_rho,
            measured_rho * 1e8,
            p0=scattering,
            bounds=bounds_rho,
            maxfev=50000,
        )
        current = np.r_[bands, scattering]
        relative_change = np.max(np.abs((current - previous) / previous))
        if first_stop is None and relative_change <= 0.1:
            first_stop = cycle
        public = np.r_[bands, scattering[:2], scattering[2:] / 300.0]
        history.append(public)
        print(
            mode,
            "cycle",
            cycle,
            "parameters",
            public.tolist(),
            "max_relative_change",
            float(relative_change),
            "S_RMSE_uV_K",
            float(np.sqrt(np.mean((seebeck(temp_s, *bands) - measured_s * 1e6) ** 2))),
            "rho_RMSE_scaled_1e8",
            float(np.sqrt(np.mean((resistivity(temp_rho, *scattering) - measured_rho * 1e8) ** 2))),
            flush=True,
        )

    spread = np.max(np.ptp(np.array(history[-4:]), axis=0) / np.abs(public))
    assert first_stop == 2
    assert spread < 1e-5
    np.testing.assert_allclose(history[first_stop - 1], public, rtol=1e-5, atol=0)
    next_bands, _ = curve_fit(
        seebeck, temp_s, measured_s * 1e6, p0=bands, bounds=bounds_s, maxfev=1000
    )
    next_scattering, _ = curve_fit(
        resistivity,
        temp_rho,
        measured_rho * 1e8,
        p0=scattering,
        bounds=bounds_rho,
        maxfev=50000,
    )
    np.testing.assert_allclose(next_bands, bands, rtol=1e-5, atol=0)
    np.testing.assert_allclose(next_scattering, scattering, rtol=1e-5, atol=0)
    print(
        mode,
        "first_legacy_stop",
        first_stop,
        "last4_relative_spread",
        float(spread),
        "stage_response_relative",
        np.abs((next_bands - bands) / bands).tolist(),
        np.abs((next_scattering - scattering) / scattering).tolist(),
    )


def main() -> None:
    print("environment", platform.python_version(), np.__version__, scipy.__version__)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for hall in (False, True):
            check_fixed_point(hall)


if __name__ == "__main__":
    main()
