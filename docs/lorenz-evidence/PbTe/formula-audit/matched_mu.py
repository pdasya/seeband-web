"""Compare at source-inferred chemical potentials, bypassing the density solver."""

import csv
from pathlib import Path

import numpy as np
from seeband_core import math_module as mm
from seeband_core.transport import band_transport

out = Path(__file__).resolve().parent
rows = []
for row in csv.DictReader((out / "inverse.csv").open()):
    t = float(row["T"])
    mu = float(row["fig5_inferred_mu_eV"])
    for intercept in (0.09, 0.18):
        edges = np.array([-intercept - 0.0004 * t, -0.36, 0])
        signs = np.array([-1, -1, 1])
        mass = np.array([0.36, 2, 0.3]) * (1 + np.array([0.5, 0, 0.5]) * (t - 300) / t)
        etas = signs * (mu - edges) / (mm.kB * t / mm.e)
        f, s, l = (  # noqa: E741
            np.array(
                [
                    band_transport(np.array([t]), np.array([eta]), sg * m, 0)[:3]
                    for eta, sg, m in zip(etas, signs, mass, strict=False)
                ]
            )
            .squeeze(-1)
            .T
        )
        g = f / (mass * np.array([19.0, 9.5, 19.0]) ** 2)
        w = g / g.sum()
        intra = w @ l * 1e8
        mixing = w @ ((s - w @ s) ** 2) * 1e8
        rows.append(
            dict(
                **row,
                gap_intercept=intercept,
                L_own=l[0] * 1e8,
                Sigma_own=l[1] * 1e8,
                C_own=l[2] * 1e8,
                intra=intra,
                mixing=mixing,
                total=intra + mixing,
            )
        )
with (out / "matched_mu.csv").open("w") as fp:
    wr = csv.DictWriter(fp, fieldnames=rows[0])
    wr.writeheader()
    wr.writerows(rows)
