# SPB Hall fit correction (P4/P12)

SPB S + ρ + R_H is enabled after fixing both #83 and its prerequisite #103.
This changes numerical results in the unreleased Physics fixes stage. Human
physicist confirmation, desktop parity (#71), and author review (#80) remain
pending. Agent review does not satisfy those requirements.

## Statistics and signs

The Hall integrals use the chemical potential μ(T) that conserves the carrier
density defined by E_F at zero temperature. The old expression used E_F at
every temperature. With unnormalised Fermi integrals and acoustic scattering,

`R_H n e = -sign(m) (3/4) F_{-1/2}(x) F_{1/2}(x) / F_0(x)^2`,

where `x = sign(m) μ(T) / T`, `n` is in m⁻³, and `e` is positive. The magnitude
approaches 1 in the degenerate limit and 3π/8 in the nondegenerate limit.
Positive mass represents electrons and negative mass represents holes.

## Fit and control scales

- The Hall amplitude is `E = -sign(m) |m|^(3/2)`, with physical mass in mₑ.
  Its inverse is `m = -sign(E) |E|^(2/3)`.
- The transform decreases with mass, so transformed bounds reverse order.
  A fit preserves the carrier branch selected by its nonzero initial mass.
- SPB Hall mass controls divide their integer value by 100, consistently
  with the other SPB modes. Default physical fit bounds are −3 to +3 mₑ.
- Mixed-scattering C is a dimensionless ratio at 300 K. The resistivity
  solver uses `300 C` in kelvin, then divides its returned value and standard
  error by 300.
- The desktop's nonexistent slider and short resistivity argument slice
  are GUI defects; the registry adapter passes the complete parameter list.

## Inputs a fit refuses, and points a curve leaves out

- **Order of the points.** μ(T) is solved from one temperature to the next,
  each from the root of the one before, and a step down to a much lower
  temperature can miss the root: [650, 300] K at E_F = 3.76 K gave R_H at
  300 K 3.7e4 times off. Every fit now sorts each quantity by temperature,
  which files already were (D22), and the Hall curve solves in ascending order
  and puts the values back. A root whose carrier density is more than 1e-6
  from the density at 0 K is NaN, not a value. The solver itself is #87.
- **Reduced potential above 700.** The Fermi integrals of order −½ and 0
  overflow past about 709, so a Hall point with μ/T above 700 is NaN, as S and
  ρ are in the other SPB modes, and the rest of the curve stays. A fit with
  such a point fails as not finite.
- **Start mass.** A mass of 0, or a start on a branch the bounds leave empty,
  fails with "The start values do not fit the bounds.". A start whose sign
  disagrees with the median sign of the R_H data fails with "The sign of the
  start band mass does not match the sign of R_H.", as it could only end at a
  bound. A mass at the branch bound of 0 is named in `at_bounds`.

The desktop mode table retains its original scales, with explicit web
overrides for the repaired mass scale and bounds. Historical desktop golden
captures remain evidence of the original implementation. New synthetic
expectations and recovery tests validate the corrected mode without claiming
a working desktop reference for it. `corrected_hall_curves` in `p4.json` replay
the desktop's recorded inputs, all with m = +1, through this code: they are
regression baselines, not independent evidence.

## What a result does not say

- **The band-mass error leaves out E_F.** The Hall stage fits the mass with
  E_F held from the S stage, while at fixed n the mass goes as 1/E_F
  (elasticity −1.00 to −1.03 on the examples). Propagating σ(E_F) gives about
  2.4 times the reported error on 01, 6 times on 02 and 2 times on 03, and a
  Monte Carlo at 1 % noise covered the true mass at 1σ in 5–13 % of runs. Read
  `parameter_errors.band_mass` as conditional on E_F.
- **"Converged" says nothing of the R_H fit.** On the three examples the
  relative RMS misfit of R_H is 5.7 (01, mass at its +3 mₑ bound, 5.14 if
  free), 2.5 (02, model nearly flat while the data change 11 times) and 0.53
  (03). With E_F fixed, a single band cannot follow R_H that changes this much
  with T. In acPhDis, A reaches its 1e7 bound on 02 and 03.

## Validation and remaining limits

The physical tests compare against independent SciPy quadrature and a
constant-density root, along a chain of temperatures from E_F/T = 667 to 0.01
in ascending, descending and shuffled order, to 1.5e-5: the asymptote of
F_1/2 above η = 19.9 is off by about 1.3/η⁴, its approximation below −9.9 by
up to 4e-6, and the worst measured is 8.5e-6. They exercise both Hall signs and the two limiting factors,
and recover known synthetic parameters for all three scattering mechanisms.
Synthetic data are model-generated inputs, not measurements.

A local check on Python 3.13.18, NumPy 2.5.4 and SciPy 1.18.1 also fitted the
three recorded example measurement sets using SPB Seebeck initial estimates
and all three scattering mechanisms. All nine fits converged and produced
finite redraws. The fitted masses were positive for `01_Fe2VAl09Si01` and
`02_SiP`, and negative for `03_AWI32_SI`. The first example reached the upper
mass bound of 3 mₑ: convergence alone does not establish physical validity.

The existing no-carrier chemical-potential issue (#106) remains flagged when
`m E_F <= 0`. The existing solver and Fermi-integral underflow limitations
are not resolved by this correction. The Hall expression here assumes the
core's default scattering exponent λ = 0.

## Reconciliation of the pre-review Hall draft

The merged P4 review fixes (`62b13a0`, PR #201) take precedence over the
initial P4 commit (`62f1477`). They already validate the mass branch and
Hall sign, identify its zero branch bound, sort fit inputs and preserve
usable curve points while marking transport overflow as NaN. Independent
quadrature tests use the documented Fermi-integral error budget above.

P8 supersedes the draft's separate Hall-only chemical-potential solver:
all paths share a signed bracketed solve with a checked normalized residual
at most 1e-12, deterministic independent temperature solves and explicit
invalid-domain/precision failures. The draft's fsolve-first fallback and
1e-8 residual check are therefore redundant. No separate Hall solver or
blanket rejection based on |E_F|/T is needed. The existing per-point check
uses the actual sign(m) μ(T)/T and keeps the established NaN behavior for
transport outside its numerical range.

The retained draft tests extend coverage to singleton and duplicate
Hall-temperature batches, both carrier signs and multi-temperature
quadrature on both sides of the −9.9 and 19.9 Fermi-integral switches.
They reuse the existing independent 1.5e-5 approximation budget rather than
the draft's unsupported 2e-6 threshold. No formula, model data, fit objective,
weight, bound or approximation tolerance was changed in this reconciliation.
The tests do not resolve the remaining physical-model limitations or supply
human physicist confirmation.
