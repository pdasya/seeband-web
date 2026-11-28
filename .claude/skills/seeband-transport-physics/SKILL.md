---
name: seeband-transport-physics
description: SeeBand's own physics contract for single and double parabolic band (SPB, DPB) thermoelectric transport. Use when reading, changing, testing, reviewing or explaining Seebeck, resistivity, Hall, Lorenz or thermal-conductivity formulas, scattering laws (acPh, dis, acPhDis, ionized), Fermi integrals, the chemical potential mu(T), band signs, mass ratios, degeneracy, parameter scales, or what a fitted parameter means physically.
---

# SeeBand transport physics

The conventions the code actually uses, the limits it must reach, and a script that checks them. Read this before judging any formula in `packages/seeband_core`. For general theory use `condensed-matter-theory`; for solver, tolerance and fit reliability use `scientific-computing`.

Golden results record what the desktop application computes, including its errors. Agreement with them shows compatibility, not physics.

## Conventions in the code

- **Energies are in kelvin.** `fermi_energy`, `band_gap`, `eta` and mu are energies divided by k_B. `fermi_energy` is a T = 0 parameter. Every carrier-statistics property at T > 0 uses mu(T).
- **Reduced potential.** x = sign(m) mu / T for a band with edge 0. A positive mass is a conduction band, a negative one a valence band. In DPB band 1 is always valence at 0, so x1 = -mu/T; band 2 sits at `band_gap` with x2 = sign(m_eff) (mu - band_gap) / T.
- **Fermi integrals are unnormalised**: F_j(x) = ∫₀^∞ t^j / (1 + e^(t - x)) dt, with no 1/Γ(j+1). Source: `fermi_integrals.py`. Mixing this with the normalised convention changes every prefactor.
- **Scattering exponent.** lambda = r_tau + 1/2, where tau ∝ ε^r_tau. The table is `SCATTERING_LAWS` in `transport.py`:

  | Name      | lambda | tau temperature power | Meaning                                                 |
  | --------- | ------ | --------------------- | ------------------------------------------------------- |
  | `acPh`    | 0      | -1                    | acoustic phonons, deformation potential                 |
  | `dis`     | 0      | 0                     | disorder, short-range alloy scattering                  |
  | `ionized` | 2      | 0                     | unscreened ionized impurities, r_tau = 3/2              |
  | `acPhDis` | 0      | mixed                 | acPh and dis per band, f_i(T) = T / (T + Θ_i), see docs |

  The conductivity temperature power is lambda + 1 + tau power. `acPhDis` is documented in `docs/physics/acphdis.md`, with Θ_1 = 300 K · C and Θ_2 = 300 K · D.

- **DPB parameters.** `m_eff` = m2/|m1|, its sign sets the type of band 2. `degen` N = N2/N1 > 0. The population weight of band 2 is N |m_eff|^(3/2). `m1` is a free absolute mass only in S + ρ + R_H. A, F are band-1 scales; B, G are band-2/band-1 ratios; C, D are tau_ph/tau_dis at 300 K. The full per-mode table, with units, is `packages/seeband_core/src/seeband_core/data/desktop_modes.json`, described in `packages/seeband_core/docs/desktop-modes.md`.
- **Constants.** `math_module.py` uses kB = 1.38064852e-23 J/K (CODATA 2014) with the exact 2019 e and h. Independent checks with `scipy.constants` differ by about 3.5e-7 relative in k_B; choose tolerances accordingly.

## Single-band formulas

With x as above and s = sign(m):

- S = -s (k_B/e) [ (lambda+2) F_(lambda+1) / ((lambda+1) F_lambda) - x ]. Holes give S > 0.
- L = (k_B/e)² [ (lambda+3) F_(lambda+2) / ((lambda+1) F_lambda) - ((lambda+2) F_(lambda+1) / ((lambda+1) F_lambda))² ].
- n = 4π (2 |m| m_e k_B T / h²)^(3/2) F_(1/2)(x), per valley (`spb_carCon` returns cm⁻³).
- r_H = R_H n e / (-s) = (3/2) F_(1/2) (2 lambda + 1/2) F_(2 lambda - 1/2) / ((lambda+1)² F_lambda²). The Hall moment uses t^(2 lambda + 1/2), hence the order 2 lambda - 1/2.
- For the ionized law, `transport.py` uses σ = A (T/300 K)^(lambda + 1 + tau power) F_lambda = A (T/300 K)³ F_2, with A in S/m. The legacy lambda = 0 kernels in `math_module.py` carry their own prefactors, but their S and L must agree with `transport.band_transport`.

## Limits to check

Expected values come from the Boltzmann (x ≪ 0) and Sommerfeld (x ≫ 0) moments, independent of the code. The leading degenerate terms have O(1/x²) corrections, so use x of a few hundred and a relative tolerance near 1e-3.

| Quantity          | x ≪ 0                                        | x ≫ 0                  |
| ----------------- | -------------------------------------------- | ---------------------- |
| \|S\| / (k_B/e)   | lambda + 2 - x                               | π² (lambda + 1) / (3x) |
| L / (k_B/e)²      | lambda + 2                                   | π²/3                   |
| r_H = \|R_H\| n e | Γ(2 lambda + 3/2) Γ(5/2) / Γ(lambda + 2)²    | 1                      |
| lambda = 0        | \|S\| = 2 - x, L = 2, r_H = 3π/8 ≈ 1.178     | r_H = 1                |
| lambda = 2        | \|S\| = 4 - x, L = 4, r_H = 315π/512 ≈ 1.933 | r_H = 1                |

k_B/e = 86.17 µV/K. Run the checks, which read only and need no data:

```sh
uv run python .claude/skills/seeband-transport-physics/scripts/check_band_limits.py
```

It checks S, L and r_H for every scattering law and both band types through `transport.band_transport`, and the lambda = 0 kernels in `math_module.py` against it, across the x = 40 switch to the analytic degenerate form. Exit status 1 means a check failed. Extend it for a new law; do not loosen a tolerance to make it pass.

Fermi energy is a T = 0 parameter, so the non-degenerate limit may be unreachable through mu(T). Call the formulas at a fixed reduced potential, as the script does.

## Two bands

- σ = σ1 + σ2, S = (σ1 S1 + σ2 S2)/σ, R_H = (R1 σ1² + R2 σ2²)/σ² (Putley sum, `docs/dpb-hall-prefactor.md`).
- κ_e is the sum of L_i σ_i T plus the bipolar term σ1 σ2 (S1 - S2)² T / σ.
- Per-band contributions `dpb_indCont_*` sum to the total; a band's own S does not.
- The weights σ_i/σ are computed in log space and must stay positive for either sign of `m_eff` (`_dpb_conductivity_weights`, `docs/dpb-positive-weights.md`).
- DPB must reduce to SPB when band 2 carries nothing, for example a very large `band_gap`. Fix `m1` when testing R_H n e.
- With equal masses, mirroring E_F → `band_gap` - E_F flips S and R_H and keeps ρ.

## mu(T)

`math_module._solve_chemical_potential` solves the signed carrier balance against the T = 0 density with `brentq` and certifies the residual; failure raises `ChemicalPotentialError` instead of returning a plausible number (`docs/chemical-potential.md`). SPB has a root only when sign(m) E_F > 0. Each temperature is solved alone, so adding or reordering temperatures must not move mu by more than 1e-9 K.

## Interpreting a fit

- A converged fit is not a material property. Report parameters that end on a bound or at their start, and trade-offs such as m_eff → 0 that removes a band (`collapsed_m_eff`).
- In S-only modes the size of the SPB mass does not enter S; only its sign does.
- Active limitations are in `packages/seeband_core/src/seeband_core/known_issues.py` and `packages/seeband_core/docs/known-issues.md`. Read them before calling an error new.
- Some supplied samples are outside both models on purpose. A poor fit is a result. Never add a sample-specific term, weight or bound to improve one.

## Changing a formula

Follow the architecture skill: write the failing limit test first, then fix every copy (all modes, all scattering laws, total and per-band curves, fit and drawn curve), update golden results, record it in the changelog and the Conventions page, and leave the physicist's confirmation to a human.
