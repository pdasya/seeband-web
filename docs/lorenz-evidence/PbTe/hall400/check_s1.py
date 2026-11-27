# ruff: noqa: T201 -- print replay results for reviewers.
"""Pei SI Eq. S1. Run with Python, numpy, scipy, matplotlib. Inputs in cm3/C."""

import csv
from pathlib import Path

import matplotlib
import numpy as np
from scipy.constants import elementary_charge as e
from scipy.optimize import brentq

matplotlib.use("Agg")
import matplotlib.pyplot as plt

out = Path(__file__).resolve().parent
a, s, a0 = 1.5, 1.1, 0.9
with (out / "figure/pei-si-s3a-summary.csv").open() as stream:
    red = {r["feature"]: r for r in csv.DictReader(stream) if r["sample"] == "PbTe"}
low = float(red["lowest_temperature"]["hall_cm3_per_c"])
peak = float(red["peak"]["hall_cm3_per_c"])
p = a0 / (e * low)
target = a0 * peak / low


def h(f, b):
    return (a * b * b * f + s * (1 - f)) / (1 + (b - 1) * f) ** 2


def stationary(b):
    return 1 / (b - 1) - 2 * s / (a * b * b - s)


def b_at_peak(target):
    return brentq(lambda b: h(stationary(b), b) - target, 2, 12)


def b_from_f(f, target):
    return brentq(lambda b: h(f, b) - target, 1, 30)


b = b_at_peak(target)
print(
    "p, normalized peak, stationary b, fL, fSigma", p, target, b, stationary(b), 1 - stationary(b)
)
print(
    "nominal p=2.4e20",
    2.4e20 * e * peak,
    b_at_peak(2.4e20 * e * peak),
    stationary(b_at_peak(2.4e20 * e * peak)),
)
for f in [0.77, 0.23, stationary(4)]:
    print("f,b=4,H,R", f, h(f, 4), h(f, 4) / (p * e))
rows = []
with (out / "s3b_400.csv").open() as stream:
    for row in csv.DictReader(stream):
        p20, q, w = map(float, row.values())
        f = 1 - q
        ratio = q * (1 - w) / (f * w)
        calc = h(f, ratio)
        assert abs(calc - (a * (1 - w) ** 2 / f + s * w * w / q)) < 1e-12
        # Show exactly which concentration is used for the ordinate in cm^3/C.
        rows.append([p20, q, w, ratio, calc, calc / (e * p20 * 1e20)])
        print("S3b: p20,q,w,b,H,R at its own p", rows[-1])
fig, ax = plt.subplots(figsize=(7.5, 4.3), layout="constrained")
f = np.linspace(0, 1, 801)
ax.plot(f, h(f, 4), label="S1 at b = 4", color="#245e83")
ax.axhline(target, label="S3(a), peak normalized to low-T Hall", color="black", ls="--")
for v, col in [(0.77, "#c04c37"), (0.23, "#1f825c")]:
    ax.plot(v, h(v, 4), "o", color=col, label=f"b = 4,  fL = {v:.2f}")
ax.plot(
    1 - rows[-1][1], rows[-1][4], marker="D", color="#9768b0", label="S3(b), nearest concentration"
)
ax.set(
    xlabel="Fraction of holes in L",
    ylabel="e p R$_H$",
    title="PbTe at 400 K · two-hole Hall equation",
    xlim=(0, 1),
    ylim=(1, 2.9),
)
ax.legend(fontsize=9)
ax.grid(alpha=0.2)
fig.savefig(out / "s1.png", dpi=175)
