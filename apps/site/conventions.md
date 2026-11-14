# Model conventions

## Neural-net initial values

P9 chooses the first supported neural-net range covered by actual Tmin and
Tmax. Paired T–S rows are sorted on a copy before preparing the degree-5
polynomial input; no measurements are removed or averaged. Network weights,
range priority and inference arithmetic are unchanged. A network estimate
is an initial value, not evidence that a model fits the sample. Original
row-order warnings remain provenance, and original desktop captures stay
unchanged.

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
