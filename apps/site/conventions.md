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
