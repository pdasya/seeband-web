# Calculation conventions

## Interpolation support

Interpolation evaluates the existing degree-10 Chebyshev fit only on the
intersection of the requested fit range and each quantity's measured
temperature range. A requested 50–800 K window with measurements spanning
25–750 K therefore produces interpolation over 50–750 K, and the interface
notes the coverage limit. Quantities keep their independent temperature grids.

There must be at least 20 K of overlap. No overlap, a single-temperature
intersection or a shorter overlap makes that quantity unavailable to a fit.
Source data are unchanged. The polynomial still uses all supplied points;
this support restriction does not cure overshoot, underdetermination or
poor physical model agreement, and interpolated points are not independent
measurements. No sample-dependent model adjustment is made.

New server interpolation does not extrapolate. Explicit legacy/external
extrapolation provenance remains flagged. Human physicist confirmation and
the #71 parity gate remain separate from this numerical-domain correction.

## Scattering conventions

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
