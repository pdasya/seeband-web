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
See the [SPB Hall fit notes](../../packages/seeband_core/docs/spb-hall-fit.md).
Human physicist confirmation remains pending.

## Result versions and provenance

[Results that changed](results-changed.md) lists the P2–P7 corrections included
in core 0.1.0 and the remaining confirmation gates.

Core `0.1.1` adds the P8 solver and domain-aware fitting described above.
Core `0.1.2` adds P9 neural-net selection from the actual temperature span.
Core `0.1.3` adds P11 pointwise mixed-scattering Seebeck weighting.
Core `0.1.4` adds P13 positive longitudinal DPB transport weights, retaining
the signed public mass ratio and carrier signs. See [positive DPB weights](../../packages/seeband_core/docs/dpb-positive-weights.md).
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
coordinates. Derived curves also convert R to r. Iterative fitting retains the
separate mass/bounds inconsistency described below (#85). The carrier-density weight is N |R|^(3/2). Longitudinal
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
The P13 [correction note](../../packages/seeband_core/docs/dpb-positive-weights.md)
records the limits and synthetic validation. This does not resolve P6's
iterative-mode output/bounds inconsistency (`dpb_loop_degeneracy`, #85).

P6 repairs the S-only mismatch; P13 corrects longitudinal negative-mass
weights, but does not resolve collapsed bands (#107) or the band diagram
(#108). P8 checks chemical-potential roots as described above. The separate
iterative-mode output/bounds inconsistency remains flagged by
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

For SPB and DPB acPhDis, C and D are dimensionless scattering ratios at 300 K.
D applies only to DPB band 2. The low-level temperature-dependent transport
functions use c = 300 K × C and d = 300 K × D. P3 (#82) applies this conversion
once at the calculation boundary for conductivity, thermal conductivity and
band contributions, as already done for resistivity and total Seebeck.

At identical parameters and temperatures, σρ = 1. DPB band conductivities sum
to total σ. Electronic κ includes the two Lorenz terms and the bipolar term
T σ₁σ₂/(σ₁+σ₂) (S₁−S₂)². Here S₁ and S₂ are each band's own Seebeck coefficient;
the plotted contributions are σᵢSᵢ/(σ₁+σ₂).

P11 (#102) uses q(T) = B (C_K + T) / ((D_K + T) |r|) at each temperature
in total DPB acPhDis Seebeck, with C_K = 300 K × C and D_K = 300 K × D.
The total equals the sum of the weighted band contributions on the same grid.
P8 supplies independent checked chemical potentials. These identities use the
existing mass coordinate r; they do not resolve nonunit-degeneracy iterative
fits or final-stage fit consistency limitations. P13 supplies positive
longitudinal weights across scattering modes; see its correction note.

The P3 correction has automated identity checks. Human physicist confirmation
and the complete #71 desktop/web comparison remain outstanding.
