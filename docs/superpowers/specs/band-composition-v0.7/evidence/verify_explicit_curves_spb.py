#!/usr/bin/env python3
"""P18 audit: explicit_curves versus independent closed SPB oracle and channel sums.

Run from a P18 checkout:
  PYTHONPATH=packages/seeband_core/src .venv/bin/python /path/to/verify_explicit_curves_spb.py
Uses scripts/verify_spb_design_coefficients.py from that checkout. No app edits.
Uses inherited core constants explicitly to isolate formula/integration errors;
current-SI versus inherited-constant compatibility is a separate question.
Checks predictions for fit-mode selectors, not optimizer convergence or fits.
"""

# ruff: noqa: T201
import runpy
from pathlib import Path

import numpy as np
from seeband_core import math_module as mm
from seeband_core.explicit_transport import explicit_curves
from seeband_core.model_interface import ExplicitBands

oracle = runpy.run_path(str(Path.cwd() / "scripts/verify_spb_design_coefficients.py"))
closed = oracle["closed"]
fd = oracle["fd"]
closed.__globals__.update(E_C=mm.e, KB_J_K=mm.kB, HBAR_J_S=mm.hbar, ME_KG=mm.me)
p = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=450.0, A=1e5, B=0.8, F=2e4, G=1.2)
ts = np.array([100.0, 300.0, 800.0])
maxima = dict(S=0.0, rho=0.0, RH=0.0, L=0.0, sigma=0.0, kappa=0.0, density_residual=0.0)
cases = 0
hall_worst = None
oracle_grid = 0.0
for config, doping, signs in [
    ("vb_vb", -2e24, (-1, -1)),
    ("vb_cb", 2e24, (-1, 1)),
    ("cb_cb", 2e24, (1, 1)),
]:
    settings = ExplicitBands(config, doping)
    mu = explicit_curves(settings, "dpb_s", p, ts, None, 2, 6, "chemical_potential")[
        "chemical_potential_k"
    ]
    for law, oracle_law in [("acPh", "acPh"), ("dis", "alloy/dis"), ("ionized", "ionized")]:
        lam = oracle["LAWS"][oracle_law][0]
        channels = [
            [
                closed(
                    signs[i] * (potential - i * 450) / t,
                    t,
                    signs[i],
                    (1.7, 0.8)[i],
                    (2, 6)[i],
                    oracle_law,
                )
                for i in range(2)
            ]
            for potential, t in zip(mu, ts, strict=True)
        ]
        for j, (potential, t) in enumerate(zip(mu, ts, strict=True)):
            for i in range(2):
                fine = closed(
                    signs[i] * (potential - i * 450) / t,
                    t,
                    signs[i],
                    (1.7, 0.8)[i],
                    (2, 6)[i],
                    oracle_law,
                    3200,
                )
                oracle_grid = max(
                    oracle_grid,
                    *(abs(a / b - 1) for a, b in zip(channels[j][i], fine, strict=True)),
                )
        for mode in ("dpb_s", "dpb_s_rho", "dpb_s_rho_rh"):
            actual = explicit_curves(settings, mode, p, ts, law, 2, 6)
            diagnostics = {}
            for kind in ("lorenz_number", "electrical_conductivity", "thermal_conductivity"):
                diagnostics.update(explicit_curves(settings, mode, p, ts, law, 2, 6, kind))
            for j, (potential, t) in enumerate(zip(mu, ts, strict=True)):
                amplitude = 1 if mode == "dpb_s" else p["F" if law == "dis" else "A"]
                relative = 1 if mode == "dpb_s" else p["G" if law == "dis" else "B"]
                factor = t if law == "dis" else (t / 300) ** 3 if law == "ionized" else 1
                weight = [1, 3 * relative / p["mass_ratio"]]
                sigma_i = [
                    amplitude * factor * weight[i] * fd(lam, signs[i] * (potential - i * 450) / t)
                    for i in range(2)
                ]
                sigma = sum(sigma_i)
                w = [x / sigma for x in sigma_i]
                ch = channels[j]
                s = sum(w[i] * ch[i][1] for i in range(2))
                rh = sum(w[i] ** 2 * ch[i][3] for i in range(2))
                lorenz = sum(w[i] * ch[i][2] + w[i] * (ch[i][1] - s) ** 2 for i in range(2))
                scale_s = sum(abs(w[i] * ch[i][1]) for i in range(2))
                scale_h = sum(abs(w[i] ** 2 * ch[i][3]) for i in range(2))
                maxima["S"] = max(maxima["S"], abs(actual["seebeck_v_per_k"][j] - s) / scale_s)
                if mode != "dpb_s":
                    maxima["rho"] = max(
                        maxima["rho"], abs(actual["resistivity_ohm_m"][j] * sigma - 1)
                    )
                if mode == "dpb_s_rho_rh":
                    hall_error = abs(actual["hall_m3_per_c"][j] - rh) / scale_h
                    if hall_error > maxima["RH"]:
                        hall_worst = (
                            config,
                            law,
                            mode,
                            float(t),
                            float(potential),
                            float(actual["hall_m3_per_c"][j]),
                            float(rh),
                            float(scale_h),
                        )
                    maxima["RH"] = max(maxima["RH"], hall_error)
                for key, name, value in [
                    ("L", "lorenz_number_w_ohm_per_k2", lorenz),
                    ("sigma", "electrical_conductivity_s_per_m", sigma),
                    ("kappa", "thermal_conductivity_w_per_m_k", sigma * t * lorenz),
                ]:
                    maxima[key] = max(maxima[key], abs(diagnostics[name][j] / value - 1))
                populations = [c[4] for c in ch]
                residual = abs(sum(signs[i] * populations[i] for i in range(2)) - doping)
                maxima["density_residual"] = max(
                    maxima["density_residual"], residual / max(sum(populations), abs(doping))
                )
            cases += 1
            print(f"PASS {config}/{law}/{mode}: 3 temperatures, N=(2,6)")
print("ORACLE 1600->3200 GRID MAX", oracle_grid)
assert oracle_grid < 1e-9
print("MAX ERRORS", {k: float(v) for k, v in maxima.items()})
print("WORST HALL (config,law,mode,T,mu_K,actual,oracle,abs_channel_scale)", hall_worst)
# Published interpolation/asymptotic FD kernels have a finite approximation budget.
assert max(v for k, v in maxima.items() if k != "density_residual") < 3e-6, maxima
assert maxima["density_residual"] < 1e-10, maxima
print(
    f"PASS: {cases} mode/configuration/scattering combinations; {cases * 3} temperature vectors; "
    "Hall error scaled by sum of absolute channel Hall terms, Seebeck similarly; "
    "same inherited constants; no optimizer or production compatibility claim beyond fixtures."
)

if maxima["RH"] > 1e-6:
    print(
        "FINDING: Hall exceeds proposed 1e-6 design budget; within existing 3e-6 regression budget."
    )
