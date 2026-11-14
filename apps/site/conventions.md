# Model conventions

## Result versions and provenance

[Results that changed](results-changed.md) lists the P2–P7 corrections included
in core 0.1.0 and the remaining confirmation gates.

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
review #80 also remains open.

## DPB mass and degeneracy

Let N = N₂/N₁. The public parameter `m_eff`, displayed as m₂/m₁, is the
signed mass ratio R = m₂/|m₁|. Its magnitude is the band-mass ratio; its sign
sets the type of band 2. The reference band 1 is hole-like. The low-level
DPB formulas receive r = R/N, the mass ratio weighted by inverse degeneracy.

In DPB S-only mode, both fitting and drawing convert R to r exactly once.
Starts, fitted values, bounds and reported uncertainties remain in public
R coordinates. The carrier-density weight is N |R|^(3/2) and the transport
weight is N/R. At N = 1 the P6 conversion is the identity.

R is the ratio of single-valley band masses, not of density-of-states
masses: entering m_d,2/m_d,1 would count N twice. The transport weight N/R
holds for λ = 0 acoustic deformation-potential scattering with the same
deformation potential and elastic constant in both bands, isotropic valleys
whose band mass serves for both density and conduction, and no inter-valley
or inter-band scattering, so that σᵢ ∝ Nᵢ/mᵢ. Other scattering gives another
weight. For R < 0 the signed weight N/R is the open #104, under which the
total conductivity vanishes at R = −N.

The separate iterative-mode output/bounds inconsistency remains flagged
by `dpb_loop_degeneracy` (#85). P6 repairs the S-only mismatch and does not
establish the correctness of negative-mass transport (#104), collapsed
bands (#107), the band diagram (#108), or chemical-potential root finding.
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

The existing total-Seebeck grid-weighting error (#102) is separate: on a
multi-point grid the total can still disagree with the sum of the corrected
band contributions. Its warning remains visible. Other known model-domain
and numerical limitations remain listed in the core's known-issues document.

The P3 correction has automated identity checks. Human physicist confirmation
and the complete #71 desktop/web comparison remain outstanding.
