"""Replay the acPh DPB example from issue #292 with independent Fermi moments.

Run from the repository root with uv run python scripts/verify_lorenz_peak.py.
The input energies and mass ratio are the rounded values in the text export.
Published PB moments: doi:10.1038/s41598-021-03760-4 (Eq. 3).
Multiband open-circuit transport: doi:10.1103/PhysRevB.95.125206.
"""

# ruff: noqa: T201 -- this command prints the numerical evidence for review.
import mpmath as mp
from seeband_core import math_module as mm
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest
from seeband_core.model_scales import BOLTZMANN_EV_PER_K, default_start

mp.mp.dps = 40
r = mp.mpf("1.19429880474")
gap = mp.mpf("0.0688736950017") / mp.mpf(str(BOLTZMANN_EV_PER_K))
ef = mp.mpf("-0.012940397676") / mp.mpf(str(BOLTZMANN_EV_PER_K))
b = mp.mpf("0.991892578249")
a = mp.mpf("59915.0350422")
kb_e = mp.mpf(str(mm.kB)) / mp.mpf(str(mm.e))


def fermi(j, x):
    return mp.re(-mp.gamma(j + 1) * mp.polylog(j + 1, -mp.exp(x)))


model = registry.get("dpb")
p = default_start(model.describe().fit_mode("dpb_s_rho_rh")) | {
    "m_eff": float(r),
    "band_gap": float(gap),
    "fermi_energy": float(ef),
    "A": float(a),
    "B": float(b),
    "m1": 1.40069265081,
}
for ts in ("50", "371.42857142857144", "800"):
    t = mp.mpf(ts)

    # 3D parabolic bands, N1=N2=1, positive gap, Ef below VB edge:
    # p(T)-n(T)=p(0). Common dimensional prefactors cancel.
    def density_residual(mu, t=t):
        return t ** mp.mpf("1.5") * (
            -fermi(mp.mpf(".5"), -mu / t) + r ** mp.mpf("1.5") * fermi(mp.mpf(".5"), (mu - gap) / t)
        ) + mp.mpf(2) / 3 * (-ef) ** mp.mpf("1.5")

    mu = mp.findroot(density_residual, (-5000, 5000), solver="bisect", maxsteps=200)
    eta = [-mu / t, (mu - gap) / t]
    f0 = [fermi(0, x) for x in eta]
    sigma = [a * f0[0], a * b / r * f0[1]]
    weights = [v / sum(sigma) for v in sigma]
    seebeck = [
        kb_e * (2 * fermi(1, eta[0]) / f0[0] - eta[0]),
        -kb_e * (2 * fermi(1, eta[1]) / f0[1] - eta[1]),
    ]
    bands = [
        kb_e**2 * (3 * fermi(2, x) / f - (2 * fermi(1, x) / f) ** 2)
        for x, f in zip(eta, f0, strict=True)
    ]
    weighted = sum(weight * band for weight, band in zip(weights, bands, strict=True))
    bipolar = weights[0] * weights[1] * (seebeck[0] - seebeck[1]) ** 2
    independent = weighted + bipolar
    result = model.calculate(
        CurveRequest("dpb_s_rho_rh", p, float(t), float(t), 1, "acPh", "lorenz_number")
    )
    core = result.curves["lorenz_number_w_ohm_per_k2"][0]
    relative_error = abs((mp.mpf(core) - independent) / independent)
    print(
        f"T={ts} K: weighted={float(weighted):.10g}, bipolar={float(bipolar):.10g}, "
        f"total={float(independent):.10g} W ohm/K^2; relative error={float(relative_error):.2g}"
    )
    assert relative_error < mp.mpf("1e-11")
