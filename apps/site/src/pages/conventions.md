---
layout: ../layouts/Prose.astro
title: Calculation conventions · SeeBand
description: How SeeBand Web solves the chemical potential, fits SPB and DPB models, and treats scattering, Hall data and the Lorenz number.
current: conventions
---

# Calculation conventions

## Chemical potential

SPB and DPB solve the signed carrier balance at each temperature with a
bracketed method in μ/T. The target density still comes from E_F at 0 K.
Each returned point has normalized density residual at most 1e-12, against
the unchanged Fermi-integral approximation; an unverified point fails
explicitly. Temperature order and repeated points do not change the solution.

SPB requires sign(m) E_F > 0. DPB with one valence and one conduction band
has a finite root even at zero net doping. Two valence bands require
E_F < max(0, E_g). Zero mass and nonpositive degeneracies are invalid.
These checks do not establish fit quality, repair transport limitations or
replace human physicist confirmation and the #71 comparison.

## SPB Hall

For the enabled SPB Hall mode, `x = sign(m) μ(T)/T`, where μ(T) conserves
the carrier density set by E_F at zero temperature. The signed mass m is in
units of mₑ: positive for electrons and negative for holes. A point with signed reduced potential
`x > 700` is outside the supported integral range and returns NaN. For
acoustic scattering,

`R_H n e = -sign(m) 3 F_{-1/2}(x) F_{1/2}(x) / (4 F_0(x)^2)`.

Here F_j are unnormalised Fermi integrals, n is the positive carrier density
in m⁻³, e is the positive elementary charge, and the scattering exponent is
λ = 0. The magnitude approaches 1 and 3π/8 in the degenerate and
nondegenerate limits, respectively.

The fitted Hall amplitude is `E = -sign(m) |m|^(3/2)` and its inverse is
`m = -sign(E) |E|^(2/3)`. Mixed-scattering `C` is dimensionless at 300 K.
Reported band-mass errors are conditional on the Seebeck-stage `E_F`.
See the [SPB Hall fit notes](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/spb-hall-fit.md).
Human physicist confirmation remains pending.

## Result versions and provenance

Core `0.2.0` defaults to `verified-sequential-v2`, with exact conditional
amplitude fitting, public-R DPB coordinates and final-stage consistency checks.
Explicit `legacy-sequential-v1` retains the previous fitting path and its
documented limitations. Algorithm provenance and diagnostics do not supply
physical acceptance. See [verified sequential fitting](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/verified-sequential-fit.md).

[Results that changed](/results-changed/) lists the P2–P7 corrections included
in core 0.1.0 and the remaining confirmation gates.

Core `0.1.1` adds the P8 solver and domain-aware fitting described above.
Core `0.1.2` adds P9 neural-net selection from the actual temperature span.
Core `0.1.3` adds P11 pointwise mixed-scattering Seebeck weighting.
Core `0.1.4` adds P13 positive longitudinal DPB transport weights, retaining
the signed public mass ratio and carrier signs. See [positive DPB weights](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/dpb-positive-weights.md).
Core version `0.1.0` is the first traceable `seeband_core` version. Earlier
results may have been produced by different corrected states while reporting
`0.0.0`; a missing version is unknown and must not be inferred from this
version. P10 adds version and provenance metadata only. It changes no formula
or fit behavior. API health, calculation and fit responses expose the core
version. Shared export headers record server, fit and curve provenance
separately. PDF exports follow the same rule: no missing version is assigned
retroactively.

This metadata does not approve a scientific release. Human physicist
confirmation and the desktop comparison tracked by #71 remain open; author
review #80 was closed at the project owner’s request; author contact and
confirmation remain pending.

## Neural-net initial values

P9 chooses the first supported neural-net range covered by the actual minimum
and maximum temperatures. Paired T–S rows are sorted on a copy before
preparing the input; no measurements are removed or averaged. A network
estimate is only a starting value, not evidence that a model fits the sample.

## DPB mass and degeneracy

Let N = N₂/N₁. The public parameter `m_eff`, displayed as m₂/m₁, is the
signed mass ratio R = m₂/|m₁|. Its magnitude is the band-mass ratio; its sign
sets the type of band 2. The reference band 1 is hole-like. The low-level
DPB formulas receive r = R/N, the mass ratio weighted by inverse degeneracy.

In DPB S-only mode, fitting and drawing convert R to r = R/N exactly once;
starts, fitted values, bounds and reported uncertainties remain in public R
coordinates. Derived curves also convert R to r. The explicit legacy iterative
route retains the mass/bounds inconsistency described below (#85); the default
verified route uses public R consistently. The carrier-density weight is N |R|^(3/2). Longitudinal
transport uses the positive mass magnitude: 1/|r| for S-only, B/|r| for
single scattering and B(C_K + T)/((D_K + T)|r|) for mixed scattering, with
the scattering factors already defined below. These weights propagate through
all longitudinal quantities and per-band contributions. At N = 1 the P6
degeneracy conversion is the identity.

R is the ratio of single-valley band masses, not of density-of-states
masses: entering m_d,2/m_d,1 would count N twice. For R > 0, the transport
weight N/R holds for λ = 0 acoustic deformation-potential scattering with
the same deformation potential and elastic constant in both bands,
isotropic valleys whose band mass serves for both density and conduction,
and no inter-valley or inter-band scattering. Under these assumptions the
positive longitudinal mass/valley prefactor is Nᵢ/|mᵢ|; band occupations
and scattering factors still enter the conductivity. This is not a formula
for the entire conductivity independent of band filling. Other scattering
mechanisms need different transport factors.

P13 corrects the negative longitudinal transport-weight issue (#104) by using
the mass magnitude. Carrier signs remain in occupations and signed density;
the Hall coefficient retains carrier signs and uses the corrected resistivity.
The P13 [correction note](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/dpb-positive-weights.md)
records the limits and synthetic validation. P19 separately resolves P6's
iterative-mode output/bounds inconsistency for the default verified route.

P6 repairs the S-only mismatch; P13 corrects longitudinal negative-mass
weights, but does not resolve collapsed bands (#107) or the band diagram
(#108). P8 checks chemical-potential roots as described above. The separate
legacy iterative-mode output/bounds inconsistency remains flagged by
`dpb_loop_degeneracy` (#85).
Human physicist confirmation and parity (#71) remain outstanding.

## Interpolation support

Interpolation evaluates the existing degree-10 Chebyshev fit only on the
intersection of the requested fit range and each quantity's measured
temperature range. A requested 50–800 K window with measurements spanning
25–750 K therefore produces interpolation over 50–750 K, and the interface
notes the coverage limit. Quantities keep their independent temperature grids.

There must be at least 20 K of overlap, and 40 K where the data narrow the
range, so that the grid has two points. No overlap, a single-temperature
intersection or a shorter overlap makes that quantity unavailable to a fit,
and the interface says which of these it was. Results and exports name the
range a fit used for a quantity the data narrowed.
Source data are unchanged. The polynomial still uses all supplied points;
this support restriction does not cure overshoot, underdetermination or
poor physical model agreement, and interpolated points are not independent
measurements. No sample-dependent model adjustment is made.

New server interpolation does not extrapolate. Explicit legacy/external
extrapolation provenance remains flagged. Human physicist confirmation and
the #71 parity gate remain separate from this numerical-domain correction.

## Scattering

Core `0.3.0` offers acoustic phonons (`acPh`), alloy disorder (`dis`) and
ionized impurities (`ionized`) for SPB and DPB, including S-only fitting.
The selected mechanism and its parameters apply throughout the temperature range.
The ionized option is the power-law approximation tau(E) proportional to E^(3/2),
without a screening or impurity-ionization model. It uses lambda=2; acPh and dis
use lambda=0 in tau proportional to T^beta E^(lambda-1/2).

For ionized impurities, sigma=A*(T/300 K)^3*F2, S uses 4 F3/(3 F2)-eta,
and Hall uses F_(7/2)/F2^2. A has units S/m; DPB B is a free relative
conductivity normalization, not an impurity-density ratio. See the
[complete formulas and conventions](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/ionized-impurities.md).

At identical parameters and temperatures, sigma*rho=1. DPB band conductivities
sum to total sigma. Electronic kappa includes the two Lorenz terms and the
bipolar term T*sigma1*sigma2/(sigma1+sigma2)*(S1-S2)^2. Plotted Seebeck
contributions are conductivity weighted. Lambda is explicit and immutable;
independent requests never change the exponent of another calculation.

The current public choices omit acPhDis and its C/D controls. Historical
P3/P11 captures and low-level functions retain the previous model for
reproduction; an old mixed-scattering result is not an ionized result.
Ionized fits use Verified. SPB numerical starting estimates use the chosen
mechanism; DPB neural estimates are unavailable for ionized impurities.
Human scientific acceptance and the #71 desktop/web comparison remain separate.

## Lorenz number

The Lorenz number is L(T) = kappa_e/(sigma*T), from the same electronic kappa
and sigma as their own curves, in W*Ohm/K^2. Charts show it in units of
L0 = pi^2/3 (k_B/e)^2 = 2.443e-8 W*Ohm/K^2; exports give both columns.
For one parabolic band, L = (k_B/e)^2 (3 F0 F2 - 4 F1^2)/F0^2 with lambda=0 for
acPh and dis: 2 (k_B/e)^2 when nondegenerate, L0 when degenerate. Ionized
impurities (lambda=2) have 4 (k_B/e)^2 when nondegenerate and the same L0.

For DPB the curve is the effective L, which includes the bipolar term and can
rise far above either band's L; each band's own L, which kappa_e weighs by its
sigma, is shown beside it. L needs sigma, so S-only modes do not offer it. The
known issues of kappa_e and sigma apply to L, and it is undefined where sigma
is zero.
