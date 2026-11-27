# ruff: noqa: T201 -- print replay results for reviewers.
"""Independent quadrature in signed electron energy, unbounded tails or a diagnostic finite window.
The finite window is a sensitivity calculation, not a claim about the authors' implementation.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.constants import elementary_charge as e
from scipy.special import expit, roots_legendre

out = Path(__file__).resolve().parent
kb = 1.38064852e-23 / e  # match core constants
T = 900.0
kt = kb * T
weight = 0.375 * 3 * np.sqrt(5)
nodes, weights = roots_legendre(384)


def band(eta, window):
    low = -window
    high = np.minimum(eta, window)
    span = np.maximum(high - low, 0.0)
    z = low + (nodes[:, None] + 1) * span / 2
    distribution = (eta - z) * expit(z) * expit(-z) * span / 2
    return np.array([weights @ (distribution * z**n) for n in range(3)])


m = pd.read_csv(out / "model.csv")
for window in [100, 10]:
    j = band(-m.mu_eV.to_numpy() / kt, window) + weight * band(
        (m.offset_eV - m.mu_eV).to_numpy() / kt, window
    )
    norm = 30000 / (weight * band(np.array([-0.06 / kt]), window)[0, 0])
    sigma = norm * j[0]
    S = -1e6 * kb * j[1] / j[0]
    L = 1e8 * kb**2 * (j[2] / j[0] - (j[1] / j[0]) ** 2)
    kappa = 1e-8 * L * sigma * T
    for name, q in [("sigma", sigma), ("S", S), ("L", L), ("kappa", kappa)]:
        if window == 100:
            print(name, "maximum relative difference vs DPB:", np.max(abs(q / m[name] - 1)))
            assert np.max(abs(q / m[name] - 1)) < 1e-10
        else:
            m["window10_" + name] = q
m[["offset_eV", "mu_eV", "window10_sigma", "window10_S", "window10_kappa", "window10_L"]].to_csv(
    out / "finite-window-diagnostic.csv", index=False
)
print(m[(m.mu_eV == 0.6) & (m.offset_eV >= 0)][["offset_eV", "S", "window10_S"]])
