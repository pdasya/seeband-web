# ruff: noqa: T201 -- print replay results for reviewers.
"""Cross-check drift mobility ratios at fixed inputs. Run next to replay.py."""

import numpy as np
import pandas as pd
from replay import D, K, N, k, out, point, quadrature
from scipy.special import expit

grid = quadrature(240)
x, dx = grid
raw = pd.read_csv(out.parent / "ref49/inset/fractions_1K.csv")
ref = raw.pivot(index=["temperature_k", "concentration_cm3"], columns="quantity", values="fraction")


def factors(T, eta):
    beta = np.array([k * T / (0.18 + 0.0004 * T), 0])[:, None]
    md = np.array([0.36 * (T / 300) ** 0.5, 2.0])
    mb = md / N[:2] ** (2 / 3)
    mc = 3 * mb / (K[:2] ** (1 / 3) * (2 + 1 / K[:2]))
    v = x - np.array(eta)[:, None]
    df = dx * expit(v) * expit(-v)
    gamma = x * (1 + beta * x)
    j = (df * 3 * gamma / ((1 + 2 * beta * x) ** 2 + 2)).sum(axis=1)
    h = (df * gamma**1.5).sum(axis=1)
    return (
        mc[1] / mc[0],
        (mb[1] / mb[0]) ** 1.5,
        (D[1] / D[0]) ** 2,
        (j[0] / h[0]) / (j[1] / h[1]),
    )


def implied(f, s, c=0):
    return f / (1 - f) * (1 - s - c) / s


rows = []
for (T, p), r in ref.iterrows():
    if T % 5:
        continue
    sol = point(T, p / 1e20, grid)
    f, s = r["p_sigma_over_p_total"], r["sigma_sigma_over_sigma_total"]
    eta = (np.array([-0.18 - 0.0004 * T, -0.36]) - sol["mu_eV"]) / (k * T)
    a, d, u, j = factors(T, eta)
    b = a * d * u * j
    assert abs(b - implied(sol["pSigma_fraction"], sol["wSigma"], sol["wC"])) < 1e-11
    wc_required = 1 - s - b * s * (1 - f) / f
    rows.append(
        dict(
            T=T,
            p20=p / 1e20,
            mc_ratio=a,
            mb_ratio_pow=d,
            D_ratio_sq=u,
            integral_ratio=j,
            drift_ratio=b,
            fig_upper=implied(f, s),
            fig_lower_reading=implied(f - 0.005, s + 0.005),
            fig_upper_reading=implied(f + 0.005, s - 0.005),
            wC_required=wc_required,
            wC_model=sol["wC"],
            figure_with_model_electrons=implied(f, s, sol["wC"]),
            both_family_mass_diagnostic=b * (N[1] / N[0]) ** (5 / 3),
        )
    )
df = pd.DataFrame(rows)
df.to_csv(out / "mobility_audit.csv", index=False)
print(df[df["T"].isin([400, 700])].round(4).to_string(index=False))
print("400 K quoted eta (1.9,1.3), b:", np.prod(factors(400, [1.9, 1.3])))
print("400 K 2.4 actual", point(400, 2.4, grid))
