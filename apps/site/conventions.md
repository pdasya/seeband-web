# Scattering conventions

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
