# ruff: noqa: T201 -- print replay results for reviewers.
"""Compare like-for-like points; never report hidden trace centers as measurements."""

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")

out = Path(__file__).resolve().parent
model = pd.read_csv(out / "model.csv").rename(columns={"mu_eV": "mu_ev", "offset_eV": "delta_e_ev"})
raw = pd.read_csv(out / "figure/digitized_curves.csv").rename(columns={"value": "source"})
rows = []
for (q, delta), group in raw.groupby(["quantity", "delta_e_ev"]):
    pred = model.loc[model.delta_e_ev == delta]
    g = group.copy()
    g["model"] = np.interp(
        g.mu_ev, pred.mu_ev, pred[{"sigma": "sigma", "seebeck": "S", "kappa_el": "kappa"}[q]]
    )
    rows.append(g)
points = pd.concat(rows)
keys = ["delta_e_ev", "mu_ev"]
s = points[points.quantity == "sigma"].set_index(keys)
k = points[points.quantity == "kappa_el"].set_index(keys)
L = pd.DataFrame(index=s.index)
scale = 1e8 / 900
L["lower"] = k.lower / s.upper * scale
L["upper"] = k.upper / s.lower.where(s.lower > 0) * scale
L["status"] = np.select(
    [(k.status == "resolved") & (s.status == "resolved"), L.upper.isna()],
    ["resolved", "no_finite_upper_bound"],
    "overlap_or_floor",
)
L["source"] = (k.source / s.source.where(s.source > 0) * scale).where(L.status == "resolved")
L["quantity"] = "L"
L["unit"] = "1e-8 W ohm/K^2"
L["model"] = k.model / s.model * scale
allrows = pd.concat([points, L.reset_index()], ignore_index=True)
allrows["trace_center"] = allrows.source.where(allrows.status == "resolved")
allrows["residual"] = allrows.model - allrows.trace_center
allrows["relative_residual_pct"] = 100 * allrows.residual / allrows.trace_center
allrows["within_envelope"] = (allrows.model >= allrows.lower) & (
    allrows.model <= allrows.upper.fillna(np.inf)
)
allrows.to_csv(out / "comparison.csv", index=False)
stats = []
for keys, g in allrows.groupby(["quantity", "delta_e_ev"]):
    r = g[g.status == "resolved"]
    stats.append(
        dict(
            quantity=keys[0],
            delta_e_ev=keys[1],
            n=len(g),
            resolved=len(r),
            in_bounds=int(g.within_envelope.sum()),
            resolved_in_bounds=int(r.within_envelope.sum()),
            finite_upper=int(g.upper.notna().sum()),
            median_abs_relative_pct=r.relative_residual_pct.abs().median(),
            max_abs_relative_pct=r.relative_residual_pct.abs().max(),
            median_abs=r.residual.abs().median(),
        )
    )
pd.DataFrame(stats).to_csv(out / "per-offset-summary.csv", index=False)
for q, g in allrows.groupby("quantity"):
    r = g[g.status == "resolved"]
    print(
        q,
        "readable",
        len(r),
        "in bounds",
        r.within_envelope.sum(),
        "all inside",
        g.within_envelope.sum(),
        "finite hi",
        g.upper.notna().sum(),
        "p50/p95/max relative %",
        r.relative_residual_pct.abs().quantile([0.5, 0.95, 1]).round(2).to_list(),
    )
print("Worst resolved out-of-bounds readings")
print(
    allrows.query('status=="resolved" and not within_envelope')[
        ["quantity", "delta_e_ev", "mu_ev", "source", "model", "lower", "upper"]
    ].head(16)
)
