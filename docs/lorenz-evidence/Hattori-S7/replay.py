"""Run with seeband_core from 84af5de52675c45ebbc139ec517873c573a4effa."""

import csv
from pathlib import Path

import numpy as np
from seeband_core import math_module as mm
from seeband_core.explicit_transport import explicit_curves
from seeband_core.fermi_integrals import fermi_integral
from seeband_core.model_interface import ExplicitBands

OUT = Path(__file__).resolve().parent
temperature = 900.0
t = np.array([temperature])
dos = (2 * mm.me * mm.kB * temperature / mm.hbar**2) ** 1.5 / (2 * np.pi**2)
curves = {
    "sigma": ("electrical_conductivity", "electrical_conductivity_s_per_m"),
    "S": ("seebeck", "seebeck_v_per_k"),
    "kappa": ("thermal_conductivity", "thermal_conductivity_w_per_m_k"),
    "L": ("lorenz_number", "lorenz_number_w_ohm_per_k2"),
    "mu_k": ("chemical_potential", "chemical_potential_k"),
}
rows = []
for g in np.linspace(4, 10, 301):
    # Hattori prescribes the chemical potential. Compute the corresponding
    # density to exercise the core density solver at exactly that potential.
    density = dos * (fermi_integral(0.5, -g) - fermi_integral(0.5, 0.0))
    settings = ExplicitBands("vb_cb", net_electron_density_per_m3=density)
    params = dict(m1=1.0, mass_ratio=1.0, A=1.0, B=1.0, band_offset_k=g * temperature)
    row = dict(gap_kbt=g)
    for name, (kind, key) in curves.items():
        row[name] = explicit_curves(settings, "dpb_s_rho", params, t, "acPh", 1, 1, kind)[key][0]
    assert abs(row["mu_k"]) < 1e-7
    assert np.isclose(row["kappa"] / (temperature * row["sigma"]), row["L"], rtol=1e-13, atol=0.0)
    rows.append(row)
for row in rows:
    for name in ("sigma", "S", "kappa", "L"):
        row[name + "_ratio"] = row[name] / rows[-1][name]
with (OUT / "model.csv").open("w") as f:
    w = csv.DictWriter(f, fieldnames=rows[0])
    w.writeheader()
    w.writerows(rows)
