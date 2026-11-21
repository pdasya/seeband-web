#!/usr/bin/env python3
"""Synthetic, conditional mass-identifiability reference; no production imports.

Run: .venv/bin/python scripts/verify_parabolic_mass_identifiability.py
Reuses charge balance from verify_mixed_scattering_design and the independently
checked SPB coefficients from verify_spb_design_coefficients. Isotropic unbounded
3D parabolas, spin 2, N excludes spin; weak-field scalar relaxation-time model.
CB s=+1, VB s=-1, charge q=-s*e. Energies (including EF(0), edges, mu) are
energy/kB [K], masses positive [m_e], n-p [m^-3], S [V/K], rho [ohm*m],
RH [m^3/C]. EF(0) sets n-p for EACH composition, not a fixed measured density.

Empirical P18 law: sigma_i=sigma0(T)*(N_i/N_1)*(b_i/M_i)*F_lambda(eta_i),
M_i=m_i/m_1, b_1=M_1=1. sigma0=A, F*T, A*(T/300K)^3 for acoustic,
alloy and ionized, respectively. A=1e5 S/m; F=A/300K S/(m*K).
This is not fixed microscopic tau: imposing microscopic mass dependence on
sigma0 or b changes the identifiability problem. Three-band empirical weights,
especially ionized, are a proposed reference law, not approved production physics.

Profiles below are conditional slices with other coordinates prescribed, NOT
optimized likelihood profiles or confidence intervals. Synthetic data are noiseless;
1 uV/K, 1% rho, 2% RH are illustrative residual scales, not measured errors.
No optimizer, production fitter, API support or physicist approval is asserted.
"""

# ruff: noqa: T201 -- standalone reproducible numerical evidence.

import math
import platform
import sys
from dataclasses import replace

import numpy as np
import scipy
from verify_band_composition_design import EV_J, KB_J_K, solve, zero_density
from verify_band_composition_design import Band as ChargeBand
from verify_mixed_scattering_design import Band, combine, potential
from verify_spb_design_coefficients import LAWS, closed, fd

TEMPERATURES_K = (100.0, 300.0, 800.0)
AMPLITUDE_S_M = 1e5


def numbers(values):
    return "[" + ", ".join(f"{v:.3e}" for v in values) + "]"


def curves(bands, bweights, ef_k, law="acPh", fixed_mu=None, panels=1600, tail=50.0):
    """Return mu and channel-sum observables; amplitude held empirical throughout."""
    assert len(bands) == len(bweights) and bweights[0] == 1
    assert all(b > 0 and math.isfinite(b) for b in bweights)
    result = []
    lam, _ = LAWS[law]
    for j, temperature in enumerate(TEMPERATURES_K):
        mu = potential(bands, temperature, ef_k) if fixed_mu is None else fixed_mu[j]
        sigma0 = AMPLITUDE_S_M * (
            1
            if law == "acPh"
            else temperature / 300
            if law == "alloy/dis"
            else (temperature / 300) ** 3
        )
        channels = []
        for band, bweight in zip(bands, bweights, strict=True):
            eta = band.s * (mu - band.edge_k) / temperature
            _, seebeck, lorenz, hall, _ = closed(
                eta, temperature, band.s, band.mass_me, band.valleys, law, panels, tail
            )
            sigma = (
                sigma0
                * band.valleys
                / bands[0].valleys
                * bweight
                / (band.mass_me / bands[0].mass_me)
                * fd(lam, eta, panels, tail)
            )
            channels.append((sigma, seebeck, lorenz, hall))
        observables = combine(channels)
        assert all(math.isfinite(x) for x in (mu, *observables)) and observables[0] > 0
        result.append((mu, *observables))
    return np.array(result)


def differences(actual, reference):
    # Columns: mu, rho, S, RH, L, |S| channel scale, |RH| channel scale.
    return (
        float(np.max(np.abs(actual[:, 0] - reference[:, 0]))),
        float(np.max(np.abs(actual[:, 1] / reference[:, 1] - 1))),
        float(np.max(np.abs(actual[:, 2] - reference[:, 2]))),
        float(np.max(np.abs(actual[:, 3] - reference[:, 3]) / reference[:, 6])),
    )


def common_mass_check():
    maximum = np.zeros(4)
    count = 0
    for signs in ((1, 1), (-1, -1), (-1, 1), (1, 1, 1), (-1, -1, -1), (-1, 1, 1)):
        bands = tuple(
            Band(s, (0, 450, -400)[i], (1.7, 0.8, 1.1)[i], (2, 6, 3)[i], 0)
            for i, s in enumerate(signs)
        )
        ef = 700 if all(s == 1 for s in signs) else -700 if all(s == -1 for s in signs) else 100
        weights = (1, 0.8, 1.3)[: len(bands)]
        for law in LAWS:
            reference = curves(bands, weights, ef, law)
            for scale in (0.25, 0.7, 4.0):
                actual = curves(
                    tuple(replace(b, mass_me=b.mass_me * scale) for b in bands), weights, ef, law
                )
                expected = reference.copy()
                expected[:, (3, 6)] *= scale**-1.5
                delta = differences(actual, expected)
                maximum = np.maximum(maximum, delta)
                assert (
                    delta[0] < 1e-8 and delta[1] < 1e-10 and delta[2] < 1e-12 and delta[3] < 1e-10
                )
                count += 1
    print(
        f"Common mass PASS: {count} cases, 2/3 bands, CB/VB/mixed, all 3 laws; "
        f"c=0.25,0.7,4; max [mu K,rho rel,S V/K,RH channel-scaled]={numbers(maximum)}"
    )
    print(
        "Fixed EF/edges/N/ratios/b/sigma0: mu,S,rho invariant, RH scales c^-3/2. "
        "Density itself scales c^3/2; this claim does not fix measured n-p."
    )


def compensation_check():
    bands = (Band(-1, 0, 1, 1, 0), Band(1, 0, 1, 1, 0))
    null = curves(bands, (1, 1), 0)
    scaled = curves(tuple(replace(b, mass_me=4) for b in bands), (1, 1), 0)
    near = curves(bands, (1, 1 + 1e-6), 0)
    assert np.max(np.abs(null[:, 3]) / null[:, 6]) < 1e-12
    assert np.max(np.abs(scaled[:, 3]) / scaled[:, 6]) < 1e-12
    fraction = float(np.max(np.abs(near[:, 3]) / near[:, 6]))
    assert 0 < fraction < 2e-6
    print(
        "Hall null PASS: symmetric VB+CB, EF=edges=0, b=(1,1): RH=0 at both masses; "
        f"b2=1+1e-6 gives max |RH|/sum|RH_i*w_i^2|={fraction:.3e}."
    )
    print(
        "Absolute mass needs informative Hall conditional on other parameters. "
        "At RH=0 it is absent; near compensation fixed absolute Hall noise "
        "suppresses sensitivity (dRH/dlog(c)=-1.5 RH)."
    )


def tradeoff_check():
    bands = (Band(1, 0, 1, 2, 0), Band(1, 450, 1.4, 3, 0), Band(1, -400, 2, 1, 0))
    alternative = (bands[0], replace(bands[1], mass_me=1.68), replace(bands[2], mass_me=1.6))
    weights = (1, 1.2, 0.8)  # b_i/M_i unchanged for i=2,3.
    reference = curves(bands, (1, 1, 1), 700)
    fixed = curves(alternative, weights, 700, fixed_mu=reference[:, 0])
    resolved = curves(alternative, weights, 700)
    d_fixed, d_resolved = differences(fixed, reference), differences(resolved, reference)
    assert d_fixed[1] < 1e-12 and d_fixed[2] < 1e-14 and d_fixed[3] > 1e-3
    assert d_resolved[0] > 1 and d_resolved[1] > 1e-3 and d_resolved[2] > 1e-7
    print(
        "b/M tradeoff PASS: m=(1,1.4,2)->(1,1.68,1.6), N=(2,3,1), "
        "edges=(0,450,-400)K, EF=700K, b=(1,1.2,0.8)."
    )
    print(
        f"  Fixed mu max [rho rel,S V/K,RH scaled]={numbers(d_fixed[1:])}; "
        f"re-solved density max [mu K,rho rel,S V/K,RH scaled]={numbers(d_resolved)}."
    )


def conditional_profiles():
    # Preserve sum N*m^1.5 for channels 2+3; at equal edges this preserves the
    # entire charge equation. Preserve both b/M ratios, including unequal N.
    masses = np.linspace(0.8, 1.75, 39)
    dos23 = 3 * 1.4**1.5 + 2**1.5
    for name, edges in (
        ("equal", (0, 0, 0)),
        ("nearly equal", (0, 1, -1)),
        ("contrasting", (0, 450, -400)),
    ):
        bands = tuple(
            Band(1, edge, mass, n, 0)
            for edge, mass, n in zip(edges, (1, 1.4, 2), (2, 3, 1), strict=True)
        )
        reference = curves(bands, (1, 1, 1), 700)
        records = []
        for mass2 in masses:
            remainder = dos23 - 3 * mass2**1.5
            assert remainder > 0
            mass3 = remainder ** (2 / 3)
            weights = (1, mass2 / 1.4, mass3 / 2)
            alternative = (
                bands[0],
                replace(bands[1], mass_me=mass2),
                replace(bands[2], mass_me=mass3),
            )
            actual = curves(alternative, weights, 700)
            # RSS per datum, with declared synthetic scales, no fitted degrees
            # of freedom or statistical confidence interpretation.
            sr = np.concatenate(
                (
                    (actual[:, 2] - reference[:, 2]) / 1e-6,
                    (actual[:, 1] / reference[:, 1] - 1) / 0.01,
                )
            )
            hall = (actual[:, 3] - reference[:, 3]) / (0.02 * np.abs(reference[:, 3]))
            records.append(
                (
                    mass2,
                    np.mean(sr**2),
                    np.mean(hall**2),
                    all(0.9 <= w <= 1.1 for w in weights),
                )
            )
        records = np.array(records)
        accepted = records[records[:, 1] <= 1]
        bounded = accepted[accepted[:, 3] == 1]
        hall_accepted = accepted[accepted[:, 2] <= 1]
        assert len(bounded) > 0 and len(hall_accepted) > 0
        if name == "equal":
            assert records[:, 1].max() < 1e-15
        if name == "nearly equal":
            assert len(accepted) == len(masses) and len(bounded) < len(accepted)
            assert len(hall_accepted) < len(accepted)
        if name == "contrasting":
            assert len(accepted) < len(masses)
        print(
            f"Conditional {name} slice: max S/rho mean squared scaled "
            f"residual={records[:, 1].max():.3e}; <=1 points S/rho={len(accepted)}/39, "
            f"S/rho AND Hall={len(hall_accepted)}/39; bounded S/rho "
            f"(b2,b3 in [0.9,1.1])={len(bounded)}/39, "
            f"M2=[{bounded[:, 0].min():.3f},{bounded[:, 0].max():.3f}]."
        )
    print(
        "Slices: CB+CB+CB, m1=1, N=(2,3,1), EF=700K, M2=0.8..1.75 step 0.025; "
        "M3=[(3*1.4^1.5+2^1.5)-3*M2^1.5]^(2/3), b=(1,M2/1.4,M3/2)."
    )
    print(
        "Bounds truncate the prescribed ridge; they do not supply information from "
        "measurements. Contrasting edges can split S/rho already; Hall need not "
        "identify every mass, edge, weight or degeneracy jointly."
    )


def refinement_check():
    bands = (Band(-1, 0, 1.7, 2, 0), Band(1, 450, 0.8, 6, 0), Band(1, -400, 1.1, 3, 0))
    maximum = np.zeros(4)
    for law in LAWS:
        coarse = curves(bands, (1, 0.8, 1.3), 100, law)
        fine = curves(bands, (1, 0.8, 1.3), 100, law, panels=3200)
        extended = curves(bands, (1, 0.8, 1.3), 100, law, panels=3200, tail=60)
        maximum = np.maximum(
            maximum, np.maximum(differences(coarse, fine), differences(fine, extended))
        )
    assert maximum[1] < 1e-8 and maximum[2] < 1e-12 and maximum[3] < 1e-8
    print(
        "Quadrature PASS: 1600->3200 panels and separate 50->60 kBT tail; "
        f"max [mu K,rho rel,S V/K,RH scaled]={numbers(maximum)}. "
        "Charge solver checks normalized residual <1e-11 at every solve."
    )
    # Independent radial-k charge solver in eV, not the FD/quad formulation.
    radial_bands = tuple(
        ChargeBand(b.s, b.edge_k * KB_J_K / EV_J, b.mass_me, valleys=b.valleys) for b in bands
    )
    errors = []
    target = zero_density(radial_bands, 100 * KB_J_K / EV_J)
    for temperature in TEMPERATURES_K:
        expected = potential(bands, temperature, 100)
        for panels, tail in ((800, 50), (1600, 50), (1600, 60)):
            mu_ev, _, _ = solve(radial_bands, target, temperature, panels, tail)
            errors.append(abs(mu_ev * EV_J / KB_J_K - expected))
    assert max(errors) < 1e-7
    print(
        "Independent radial-k charge PASS: FD vs 800/1600 panels, 50/60 kBT tails; "
        f"max mu error={max(errors):.3e} K."
    )


def main():
    if not __debug__:
        sys.exit("Run without -O: this evidence requires enabled assertions.")
    print(
        f"SYNTHETIC CONDITIONAL MASS REFERENCE; Python {platform.python_version()}, "
        f"NumPy {np.__version__}, SciPy {scipy.__version__}"
    )
    print(
        f"T={TEMPERATURES_K} K; sigma0(300K)={AMPLITUDE_S_M:g} S/m; "
        "energies/kB [K], m [me], S [V/K], rho [ohm*m], RH [m^3/C]."
    )
    print(
        "Illustrative residual scales: S=1 uV/K, rho=1%, RH=2% of nonzero "
        "synthetic reference. S/rho gate: mean(6 scaled squares)<=1; +Hall also "
        "requires mean(3 Hall scaled squares)<=1. Bounded S/rho is a separate subset."
    )
    common_mass_check()
    compensation_check()
    tradeoff_check()
    conditional_profiles()
    refinement_check()
    print(
        "PASS selected synthetic references only; no production numerical changes, "
        "statistical intervals, global identifiability or human physicist confirmation."
    )


if __name__ == "__main__":
    main()
