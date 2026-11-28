"""Profile one constant acoustic prefactor ratio per composition against S and weak-field Hall."""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from forward_model import forward
from scipy.optimize import minimize_scalar
from scipy.special import expit

HERE = Path(__file__).resolve().parent
SAMPLES = ((0.01, 1.8e20, "x001"), (0.02, 4.7e20, "x002"), (0.03, 7.6e20, "x003"))
CHANNELS = {
    "S": ("measured_seebeck.csv", "seebeck_uv_per_k"),
    "Hall": ("measured_hall.csv", "hall_coefficient_cm3_per_c"),
}


def read_points(x):
    points = []
    for channel, (filename, column) in CHANNELS.items():
        with (HERE / filename).open() as f:
            for row in csv.DictReader(f):
                if float(row["na_fraction"]) == x:
                    points.append((channel, float(row["temperature_k"]), float(row[column])))
    labels, temperatures, observations = zip(*points, strict=True)
    return np.array(labels), np.array(temperatures), np.array(observations)


def prediction(bands, labels, log_w):
    # Form both conductivity fractions independently to retain an almost dark channel.
    log_ratio = log_w + np.log(bands["g_sigma"]) - np.log(bands["g_l"])
    a, b = expit(-log_ratio), expit(log_ratio)
    return np.where(
        labels == "S",
        a * bands["s_l_uv_k"] + b * bands["s_sigma_uv_k"],
        a**2 * bands["rh_l_cm3_c"] + b**2 * bands["rh_sigma_cm3_c"],
    )


def rms(values):
    return np.sqrt(np.mean(values**2))


def profile(bands, labels, measured, channels):
    # Equal contribution from each curve, irrespective of units and number of points.
    weights = np.zeros_like(measured)
    for channel in channels:
        mask = labels == channel
        weights[mask] = 1 / (mask.sum() * rms(measured[mask]) ** 2)

    def loss(u):
        return np.dot(weights, (prediction(bands, labels, u) - measured) ** 2)

    # Each band crossover is at log(g_l/g_sigma). Include all observed crossovers
    # plus 40 e-folds on either side and evaluate the two exact one-channel limits.
    crossover = np.log(bands["g_l"]) - np.log(bands["g_sigma"])
    lo, hi = min(crossover) - 40, max(crossover) + 40

    def search(step):
        grid = np.linspace(lo, hi, int(np.ceil((hi - lo) / step)) + 1)
        values = np.array([loss(z) for z in grid])
        interior = np.where((values[1:-1] < values[:-2]) & (values[1:-1] <= values[2:]))[0] + 1
        candidates = [-np.inf, np.inf, lo, hi]
        for i in interior:
            result = minimize_scalar(
                loss, bounds=(grid[i - 1], grid[i + 1]), method="bounded", options={"xatol": 1e-11}
            )
            if not result.success:
                raise RuntimeError(result.message)
            candidates.append(result.x)
        return min(candidates, key=loss)

    optimum = search(0.125)
    coarse = search(0.25)
    if not np.isclose(loss(optimum), loss(coarse), rtol=1e-8, atol=1e-14):
        raise ArithmeticError("Profile refinement failed")
    if not np.isfinite(loss(optimum)):
        raise ArithmeticError("Nonfinite best residual")
    return optimum


def check_dark_band():
    bands = forward([30.0], 1.8e20)
    equal_conductance = float(np.log(bands["g_l"][0] / bands["g_sigma"][0]))
    labels = np.array(["S"])
    target = (bands["s_l_uv_k"] + bands["s_sigma_uv_k"]) / 2
    recovered = profile(bands, labels, target, ["S"])
    assert abs(recovered - equal_conductance) < 1e-6


def report(x, case, t, obs, labels, model, published, residual_rows):
    selected = {}
    for channel in ("S", "Hall", "joint"):
        include = CHANNELS if channel == "joint" else [channel]
        selected[channel] = profile(model, labels, obs, include)
    joint = selected["joint"]
    pred = prediction(model, labels, joint)
    ratios = {k: np.exp(z) for k, z in selected.items()}
    sys.stdout.write(
        f"\nx={x:.2f} {case}  w2 joint={ratios['joint']:.5g} "
        f"S-only={ratios['S']:.5g} Hall-only={ratios['Hall']:.5g}\n"
    )
    mapped = (t >= published[0, 0]) & (t <= published[-1, 0])
    # Figure 7(d) supplies f0 for the authors' moving bands only; no extrapolation below 300 K.
    interp = np.interp(t, published[:, 0], published[:, 1])
    ref = prediction(model, labels, -np.log(3 * interp))
    has_ref = mapped & (case == "paper")
    for name in CHANNELS:
        mask = labels == name
        a, y = pred[mask], obs[mask]
        err = a - y
        ti = t[mask]
        i = np.argmax(abs(err))
        sys.stdout.write(
            f"  {name:4} N={len(y)} T={min(ti):.1f}..{max(ti):.1f} K "
            f"RMSE={rms(err):.5g} nRMSE={rms(err) / rms(y) * 100:.2f}% "
            f"max_abs={abs(err[i]):.5g} at {ti[i]:.1f} K\n"
        )
        if name == "Hall":
            sys.stdout.write(
                f"  Hall maximum on measured grid: observed {ti[np.argmax(y)]:.1f} K "
                f"({max(y):.5g}), constant {ti[np.argmax(a)]:.1f} K ({max(a):.5g}); "
                f"last observed/predicted {y[np.argmax(ti)]:.5g}/{a[np.argmax(ti)]:.5g}\n"
            )
        if np.any(mask & has_ref):
            both = mask & has_ref
            sys.stdout.write(
                f"  {name:4} Fig7d overlap N={both.sum()} "
                f"RMSE constant={rms(pred[both] - obs[both]):.5g} "
                f"published f0(T)={rms(ref[both] - obs[both]):.5g}\n"
            )
    for i in range(len(obs)):
        residual_rows.append(
            (
                x,
                case,
                labels[i],
                f"{t[i]:.2f}",
                f"{obs[i]:.8g}",
                f"{pred[i]:.8g}",
                f"{pred[i] - obs[i]:.8g}",
                f"{ref[i]:.8g}" if has_ref[i] else "",
            )
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--curves", type=Path, help="Write pointwise predictions and residuals (CSV)"
    )
    args = parser.parse_args()
    check_dark_band()
    residual_rows = []
    paper = np.genfromtxt(HERE / "published_f0.csv", delimiter=",", names=True)
    for x, density, col in SAMPLES:
        labels, t, obs = read_points(x)
        unique, back = np.unique(t, return_inverse=True)
        for case in ("paper", "fixed"):
            options = {} if case == "paper" else {"freeze_structure_at_k": 300, "anisotropy_l": 1.0}
            bands = forward(unique, density, **options)
            keys = ("g_l", "g_sigma", "s_l_uv_k", "s_sigma_uv_k", "rh_l_cm3_c", "rh_sigma_cm3_c")
            model = {key: np.asarray(bands[key])[back] for key in keys}
            report(
                x,
                case,
                t,
                obs,
                labels,
                model,
                np.column_stack((paper["temperature_k"], paper[col])),
                residual_rows,
            )
    if args.curves:
        with args.curves.open("w", newline="") as f:
            out = csv.writer(f, lineterminator="\n")
            out.writerow(
                (
                    "composition",
                    "structure",
                    "observable",
                    "temperature_k",
                    "observed",
                    "constant_w2",
                    "residual_model_minus_observed",
                    "published_f0_interpolated",
                )
            )
            out.writerows(residual_rows)


if __name__ == "__main__":
    main()
