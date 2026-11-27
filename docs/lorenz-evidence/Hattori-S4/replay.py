# ruff: noqa: T201 -- print replay results for reviewers.
"""SeeBand VB+VB, Hattori S4d-f. No digitized data used as input."""

import csv
from pathlib import Path

import numpy as np
from seeband_core import math_module as mm
from seeband_core.explicit_transport import explicit_curves
from seeband_core.fermi_integrals import fermi_integral
from seeband_core.model_interface import ExplicitBands

OUT = Path(__file__).resolve().parent
T = 900.0
KT = mm.kB * T / mm.e
# Table 1; masses are per valley. Only their ratio enters transport.
ML, MH = 0.34 / 5, 0.34
NL, NH = 4, 12
WEIGHT = 0.375 * (NH / NL) * np.sqrt(MH / ML)
B = WEIGHT * (MH / ML) / (NH / NL)
# Eq. 16 for the heavy band alone, reused with acoustic spectral exponent 1.
A = 30000.0 / (WEIGHT * np.logaddexp(0.0, -0.060 / KT))
DOS = (2 * mm.me * mm.kB * T / mm.hbar**2) ** 1.5 / (2 * np.pi**2)


def point(de, mu):
    eta_low = -mu / KT
    eta_heavy = (de - mu) / KT
    p = DOS * (
        NL * ML**1.5 * fermi_integral(0.5, eta_low) + NH * MH**1.5 * fermi_integral(0.5, eta_heavy)
    )
    settings = ExplicitBands("vb_vb", net_electron_density_per_m3=-p)
    params = dict(m1=ML, mass_ratio=MH / ML, A=A, B=B, band_offset_k=de * T / KT)

    def calc(kind):
        return explicit_curves(settings, "dpb_s_rho", params, np.array([T]), "acPh", NL, NH, kind)

    recovered = calc("chemical_potential")["chemical_potential_k"][0] * KT / T
    assert abs(recovered - mu) < 1e-10
    meas = calc("measured")
    sigma = 1 / meas["resistivity_ohm_m"][0]
    S = meas["seebeck_v_per_k"][0] * 1e6
    vals = calc("lorenz_number")
    L = vals["lorenz_number_w_ohm_per_k2"][0]
    kappa = calc("thermal_conductivity")["thermal_conductivity_w_per_m_k"][0]
    assert abs(kappa / (sigma * T) / L - 1) < 1e-12
    gl, gh = np.logaddexp(0.0, eta_low), WEIGHT * np.logaddexp(0.0, eta_heavy)
    own = (
        gl * vals["lorenz_number_band_1_w_ohm_per_k2"][0]
        + gh * vals["lorenz_number_band_2_w_ohm_per_k2"][0]
    ) / (gl + gh)
    return dict(
        offset_eV=de,
        mu_eV=mu,
        sigma=sigma,
        S=S,
        kappa=kappa,
        L=L * 1e8,
        L_intrinsic=own * 1e8,
        L_hole_mixing=(L - own) * 1e8,
    )


if __name__ == "__main__":
    with (OUT / "model.csv").open("w") as f:
        w = None
        for de in np.arange(-5, 6) / 10:
            for mu in np.arange(-800, 651, 5) / 1000:
                row = point(de, mu)
                if w is None:
                    w = csv.DictWriter(f, fieldnames=row)
                    w.writeheader()
                w.writerow(row)
    print("heavy/light spectral weight, A (S/m), B:", WEIGHT, A, B)
