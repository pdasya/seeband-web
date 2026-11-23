#!/usr/bin/env python3
"""Independent synthetic evidence for a proposed 1–3 band design, not production.

Run: python scripts/verify_band_composition_design.py (standard library only).
3D isotropic, unbounded bands; spin 2, valley count excludes spin. Edges/mu
are eV, mass is positive in m_e, alpha >= 0 in eV^-1. CB s=+1, VB s=-1;
epsilon*(1+alpha*epsilon)=hbar^2*k^2/(2*m), E=edge+s*epsilon.
At most one band has alpha>0. This numerical script cannot distinguish a
declared Kane band with alpha=0 from a parabola; the proposed API must enforce
the limit by explicit band type, including Kane's alpha=0 limiting case.
T=0 E_F fixes D=n-p. Finite-T mu solves the same signed excess density.
Radial k-space integration uses 2*4*pi/(2*pi)^3, independently of core code.
The optional transport evidence uses constant tau=1e-14 s for every band:
sigma=e^2*tau/3 * integral(v^2*(-df/dE) d^3k/(2*pi)^3), spin included.
This is NOT acPh/dis/ionized scattering, a fitted amplitude, or a model fit.
Fixtures are synthetic. No production imports, numerical results or APIs change.
"""

# ruff: noqa: T201 -- executable evidence reports deterministic results to stdout.

import math
import platform
from dataclasses import dataclass, replace
from itertools import permutations

EV_J = 1.602176634e-19
KB_J_K = 1.380649e-23
HBAR_J_S = 1.054571817e-34
ME_KG = 9.1093837139e-31
TAU_S = 1e-14


@dataclass(frozen=True)
class Band:
    s: int
    edge_ev: float
    mass_me: float
    alpha_per_ev: float = 0.0
    valleys: int = 1

    def __post_init__(self):
        if self.s not in (-1, 1) or self.mass_me <= 0 or self.alpha_per_ev < 0:
            raise ValueError("require s=+/-1, positive mass, nonnegative alpha")
        if isinstance(self.valleys, bool) or not isinstance(self.valleys, int) or self.valleys < 1:
            raise ValueError("require a positive integer valley count excluding spin")


def zero_density(bands, ef_ev):
    """Occupied CB electrons minus missing VB electrons at zero temperature."""
    contributions = []
    for b in bands:
        eps_ev = max(0.0, b.s * (ef_ev - b.edge_ev))
        kf = (
            math.sqrt(2 * b.mass_me * ME_KG * EV_J * eps_ev * (1 + b.alpha_per_ev * eps_ev))
            / HBAR_J_S
        )
        contributions.append(b.s * b.valleys * kf**3 / (3 * math.pi**2))
    return math.fsum(contributions)


def radial_integrals(b, mu_ev, temperature_k, panels=800, tail=50.0):
    """Composite Simpson directly in k/k_thermal; return (population, sigma)."""
    thermal_ev = KB_J_K * temperature_k / EV_J
    eta = b.s * (mu_ev - b.edge_ev) / thermal_ev
    upper_ev = (max(eta, 0.0) + tail) * thermal_ev
    upper = math.sqrt(upper_ev * (1 + b.alpha_per_ev * upper_ev) / thermal_ev)
    kthermal = math.sqrt(2 * b.mass_me * ME_KG * KB_J_K * temperature_k) / HBAR_J_S
    populations, currents = [], []
    for j in range(panels + 1):
        x = upper * j / panels
        # Rationalized positive Kane root is regular at alpha=0.
        eps_ev = (
            2 * thermal_ev * x * x / (1 + math.sqrt(1 + 4 * b.alpha_per_ev * thermal_ev * x * x))
        )
        z = eps_ev / thermal_ev - eta
        t = math.exp(-abs(z))
        f = t / (1 + t) if z >= 0 else 1 / (1 + t)
        velocity = HBAR_J_S * kthermal * x / (b.mass_me * ME_KG * (1 + 2 * b.alpha_per_ev * eps_ev))
        weight = 1 if j in (0, panels) else (4 if j % 2 else 2)
        populations.append(weight * x * x * f)
        # Stable Fermi window avoids cancellation of 1-f in degenerate cases.
        currents.append(weight * x * x * velocity**2 * t / (1 + t) ** 2)
    measure = b.valleys * kthermal**3 / math.pi**2 * upper / (3 * panels)
    return (
        measure * math.fsum(populations),
        measure * math.fsum(currents) * EV_J**2 * TAU_S / (3 * KB_J_K * temperature_k),
    )


def solve(bands, target_per_m3, temperature_k, panels=800, tail=50.0):
    if not 1 <= len(bands) <= 3 or temperature_k <= 0:
        raise ValueError("require 1–3 bands and T>0")
    if sum(b.alpha_per_ev > 0 for b in bands) > 1:
        raise ValueError("require at most one positive-alpha Kane band")
    signs = {b.s for b in bands}
    if len(signs) == 1 and next(iter(signs)) * target_per_m3 <= 0:
        raise ValueError("single carrier sign requires nonzero target of the same sign")

    def balance(mu):
        values = [radial_integrals(b, mu, temperature_k, panels, tail)[0] for b in bands]
        return math.fsum(b.s * n for b, n in zip(bands, values, strict=True)) - target_per_m3

    width = max(1.0, *(abs(b.edge_ev) for b in bands))
    lo, hi = -width, width
    while balance(lo) > 0 or balance(hi) < 0:
        lo, hi = 2 * lo, 2 * hi
    for _ in range(100):
        mid = (lo + hi) / 2
        if balance(mid) < 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-14:
            break
    mu = (lo + hi) / 2
    values = [radial_integrals(b, mu, temperature_k, panels, tail) for b in bands]
    residual = abs(balance(mu)) / max(abs(target_per_m3), math.fsum(n for n, _ in values))
    assert residual < 2e-11, residual
    return mu, values, residual


def main():
    print(f"SYNTHETIC DESIGN EVIDENCE; Python {platform.python_version()}; stdlib only")
    print("D=n-p [m^-3]; edges/mu/E_F [eV]; sigma fractions: constant tau only")
    vb, cb = Band(-1, 0.0, 1.2), Band(1, 0.2, 0.3, 1.0, 2)
    third = Band(-1, -0.06, 0.7)
    try:
        solve((vb, cb, replace(third, alpha_per_ev=0.5)), 0.0, 300.0)
    except ValueError as error:
        assert "at most one" in str(error)
    else:
        raise AssertionError("two positive-alpha Kane bands must be rejected")
    print("composition guard PASS: two positive-alpha Kane bands rejected")
    # At one inverse nanometre, a free-electron parabola rises by 38.10 meV.
    # The public horizontal coordinate divides the physical value by 10 / nm.
    for plotted_k in (-0.1, 0.1):
        k_per_m = plotted_k * 1.0e10
        kinetic_ev = HBAR_J_S**2 * k_per_m**2 / (2 * ME_KG * EV_J)
        assert math.isclose(kinetic_ev, 0.03809982, rel_tol=1e-6)
        for alpha_per_ev in (0.0, 1.0):
            u = 2 * kinetic_ev / (1 + math.sqrt(1 + 4 * alpha_per_ev * kinetic_ev))
            assert math.isclose(u * (1 + alpha_per_ev * u), kinetic_ev, rel_tol=1e-12)
    print("diagram scale PASS: dimensionless +/-0.1 = +/-1 nm^-1; parabolic and Kane")
    for invalid in (0, -1, 1.5, True):
        try:
            replace(vb, valleys=invalid)
        except ValueError as error:
            assert "positive integer" in str(error)
        else:
            raise AssertionError(f"invalid valley count accepted: {invalid!r}")
    print("valley count PASS: positive integers required; fractional, zero and negative rejected")
    max_residual = max_grid_mu = max_grid_observable = max_tail_observable = 0.0
    for name, bands in (
        ("gap-2", (vb, cb)),
        ("gap-3", (vb, cb, third)),
        ("touch-3", (vb, replace(cb, edge_ev=0.0), third)),
    ):
        ef_choices = (0.04, 0.16) if name.startswith("gap") else (0.0,)
        targets = [zero_density(bands, ef) for ef in ef_choices]
        assert all(d == 0.0 for d in targets)
        for temperature_k in (150.0, 300.0, 600.0):
            mu, values, residual = solve(bands, targets[0], temperature_k)
            fine_mu, fine, _ = solve(bands, targets[0], temperature_k, 1600)
            _, longer_tail, _ = solve(bands, targets[0], temperature_k, 1600, 60.0)
            max_residual = max(max_residual, residual)
            max_grid_mu = max(max_grid_mu, abs(mu - fine_mu))
            for coarse, refined, extended in zip(values, fine, longer_tail, strict=True):
                assert all(value > 0 for value in coarse)
                for a, b, c in zip(coarse, refined, extended, strict=True):
                    max_grid_observable = max(max_grid_observable, abs(a / b - 1))
                    max_tail_observable = max(max_tail_observable, abs(b / c - 1))
            for target in targets[1:]:
                assert solve(bands, target, temperature_k)[0] == mu
            for order in permutations(bands):
                assert solve(order, 0.0, temperature_k)[0] == mu
            fractions = [sigma / math.fsum(s for _, s in values) for _, sigma in values]
            print(
                f"{name} T={temperature_k:.0f} mu={mu:+.9f} "
                f"populations={[f'{n:.6e}' for n, _ in values]} "
                f"sigma_fraction={[round(f, 6) for f in fractions]} residual={residual:.2e}"
            )
    assert max_grid_mu < 1e-10 and max_grid_observable < 1e-8 and max_tail_observable < 1e-8

    # Independent exact parabolic finite-T anchor at mu=edge: FD integral value.
    # Integral x^2/(1+exp(x^2)) dx = sqrt(pi)/4*(1-1/sqrt(2))*zeta(3/2).
    parabolic = Band(1, 0.0, 1.0)
    n, sigma = radial_integrals(parabolic, 0.0, 300.0)
    kthermal = math.sqrt(2 * ME_KG * KB_J_K * 300) / HBAR_J_S
    exact_n = (
        kthermal**3
        / math.pi**2
        * math.sqrt(math.pi)
        / 4
        * (1 - 1 / math.sqrt(2))
        * 2.612375348685488
    )
    assert abs(n / exact_n - 1) < 1e-10
    assert abs(sigma / (n * EV_J**2 * TAU_S / ME_KG) - 1) < 1e-10
    mass_n = radial_integrals(replace(parabolic, mass_me=4), 0.0, 300.0)[0]
    kane_n = radial_integrals(replace(parabolic, alpha_per_ev=1e-9), 0.0, 300.0)[0]
    assert abs(mass_n / n - 8) < 1e-12 and abs(kane_n / n - 1) < 1e-9
    try:
        replace(parabolic, mass_me=0)
    except ValueError:
        pass
    else:
        raise AssertionError("zero mass must be rejected")
    one_target = zero_density((parabolic,), 0.05)
    one_mu, _, _ = solve((parabolic,), one_target, 300.0)
    crossing = [zero_density((vb, cb), ef) for ef in (-0.05, 0.1, 0.25)]
    assert crossing[0] < 0 == crossing[1] < crossing[2]
    print(
        f"limits PASS: alpha->0 relative delta={abs(kane_n / n - 1):.3e}; "
        f"mass x4 -> density x{mass_n / n:.1f}; m=0 rejected; "
        f"parabolic exact n relative error={abs(n / exact_n - 1):.3e}; sigma=n e^2 tau/m"
    )
    print(
        f"one band: E_F=0.05 D={one_target:.6e} mu(300 K)={one_mu:.9f}; "
        f"signed crossing D={crossing}"
    )
    print(
        f"PASS: gap E_F equivalence, all permutations; max normalized residual={max_residual:.3e}; "
        f"800->1600 panels: delta_mu={max_grid_mu:.3e} eV, "
        f"relative n/sigma delta={max_grid_observable:.3e}; "
        f"separate 50->60 kBT tails: relative n/sigma delta={max_tail_observable:.3e}"
    )
    print(
        "Limits: selected positive-T fixtures; alpha>=0; no anisotropy, finite bandwidth, "
        "Hall/Seebeck, production scattering, fitting or identifiability claims. "
        "Human physics confirmation remains separate."
    )


if __name__ == "__main__":
    main()
