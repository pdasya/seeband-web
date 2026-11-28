"""Check SeeBand single-band transport against analytic limits.

Run from the repository root:

    uv run python .claude/skills/seeband-transport-physics/scripts/check_band_limits.py

Expected values are derived independently from the Boltzmann-limit and
Sommerfeld-limit moments of x^(lambda+1) (-df/dx), with lambda = r_tau + 1/2.
They are not taken from golden results. The script reads only; it writes nothing.
Exit status 1 means at least one check failed.
"""

# Diagnostic CLI: it prints check results and reads no measurements.
# ruff: noqa: T201

import sys
from math import gamma, pi

import numpy as np
from seeband_core import math_module as mm
from seeband_core.transport import SCATTERING_LAWS, band_transport

K_OVER_E_UV = mm.kB / mm.e * 1e6  # 86.17 µV/K
NONDEGENERATE_X = -30.0
DEGENERATE_X = 200.0
TEMPERATURE_K = 300.0
failures: list[str] = []


def check(label: str, actual: float, expected: float, rel_tol: float) -> None:
    error = abs(actual - expected) / abs(expected)
    status = "ok  " if error <= rel_tol else "FAIL"
    if status == "FAIL":
        failures.append(label)
    print(f"{status} {label:<52} actual {actual:12.6g}  expected {expected:12.6g}  rel {error:.1e}")


def hall_factor(x: float, mass: float, lam: float) -> float:
    """Hall factor r_H = |R_H| n e for one band at reduced potential x, with the core's density.

    Also records whether R_H has the carrier sign: negative for electrons, positive for holes.
    """
    temperature = np.array([TEMPERATURE_K])
    _, _, _, hall = band_transport(temperature, np.array([x]), mass, lam)
    eta_k = np.sign(mass) * x * TEMPERATURE_K
    density_m3 = mm.spb_carCon(eta_k, mass, TEMPERATURE_K) * 1e6
    check(
        f"sign of R_H, mass {mass:+g}, x={x:g}", float(np.sign(hall[0])), -float(np.sign(mass)), 0.0
    )
    return float(abs(hall[0]) * density_m3 * mm.e)


print(f"k_B/e = {K_OVER_E_UV:.4f} µV/K\n")
for name in ("acPh", "dis", "ionized"):
    lam = SCATTERING_LAWS[name].energy_lambda
    print(f"-- scattering {name}: lambda = {lam:g}")
    for mass in (1.0, -1.0):
        band = "conduction" if mass > 0 else "valence"
        t = np.array([TEMPERATURE_K, TEMPERATURE_K])
        x = np.array([NONDEGENERATE_X, DEGENERATE_X])
        _, seebeck, lorenz, _ = band_transport(t, x, mass, lam)
        s_units = seebeck / (mm.kB / mm.e)
        l_units = lorenz / (mm.kB / mm.e) ** 2
        # Sign: holes (valence, mass < 0) give S > 0.
        check(f"{band} sign of S", float(np.sign(s_units[0])), -float(np.sign(mass)), 0.0)
        check(
            f"{band} |S|, x={NONDEGENERATE_X:g}", abs(s_units[0]), lam + 2 - NONDEGENERATE_X, 1e-9
        )
        check(
            f"{band} |S|, x={DEGENERATE_X:g}",
            abs(s_units[1]),
            pi**2 * (lam + 1) / (3 * DEGENERATE_X),
            2e-3,
        )
        check(f"{band} L, x={NONDEGENERATE_X:g}", l_units[0], lam + 2, 1e-9)
        check(f"{band} L, x={DEGENERATE_X:g}", l_units[1], pi**2 / 3, 2e-3)
        r_h_nondegenerate = gamma(2 * lam + 1.5) * gamma(2.5) / gamma(lam + 2) ** 2
        check(
            f"{band} R_H n e, x={NONDEGENERATE_X:g}",
            hall_factor(NONDEGENERATE_X, mass, lam),
            r_h_nondegenerate,
            1e-6,
        )
        check(
            f"{band} R_H n e, x={DEGENERATE_X:g}", hall_factor(DEGENERATE_X, mass, lam), 1.0, 2e-3
        )
    print()

# The historical lambda = 0 kernels in math_module must agree with transport.py.
x = np.array([NONDEGENERATE_X, -2.0, 0.0, 3.0, 39.9, 40.1, DEGENERATE_X])
t = np.full_like(x, TEMPERATURE_K)
_, s_generic, l_generic, _ = band_transport(t, x, 1.0, 0.0)
s_legacy = mm._band_seebeck(x, 1.0)
l_legacy = mm._band_lorenz(x)
print("-- math_module lambda = 0 kernels against transport.band_transport")
for xi, a, b, c, d in zip(x, s_legacy, s_generic, l_legacy, l_generic, strict=True):
    check(f"S at x={xi:g}", a, b, 1e-9)
    check(f"L at x={xi:g}", c, d, 1e-9)

print()
if failures:
    print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
    sys.exit(1)
print("All checks passed.")
