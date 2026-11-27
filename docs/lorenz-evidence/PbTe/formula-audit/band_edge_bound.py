"""Compare Eq. (1) on Fig. 5(c) at its own energy markers at 850 K.
No assumed density, relative conductivity amplitudes, or Figure 6 color mapping.
If the conduction edge is held at zero and C alone is below the target, at least
one hole band must reach the target; invert the acoustic SPB function for that edge.
"""

import csv
from pathlib import Path

from scipy.constants import Boltzmann, elementary_charge
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import expit

out = Path(__file__).resolve().parent
kt = Boltzmann / elementary_charge * 850


def ell(eta):
    def moment(n):
        return quad(
            lambda x: x * (x - eta) ** n * expit(x - eta) * expit(eta - x), 0, 100, epsabs=1e-14
        )[0]

    a, b, c = [moment(n) for n in range(3)]
    return (Boltzmann / elementary_charge) ** 2 * (c / a - (b / a) ** 2) * 1e8


rows = []
for r in csv.DictReader((out / "slices.csv").open()):
    if (r["panel"], r["temperature_k"], r["style"]) != ("5c", "850", "dotted"):
        continue
    mu = float(r["fermi_level_ev"])
    target = float(r["lorenz_1e8"])
    own = [ell((edge - mu) / kt) for edge in [-0.43, -0.36]] + [ell(mu / kt)]
    edge_required = mu + kt * brentq(lambda h: ell(h) - target, -12, 10)  # noqa: B023
    rows.append(
        dict(
            fig5_marker=r["color"],
            mu_eV=mu,
            dotted=target,
            L_own=own[0],
            Sigma_own=own[1],
            C_own=own[2],
            excess=target - max(own),
            min_valence_edge_eV=edge_required,
        )
    )
with (out / "edge-bound.csv").open("w") as f:
    wr = csv.DictWriter(f, fieldnames=rows[0])
    wr.writeheader()
    wr.writerows(rows)
