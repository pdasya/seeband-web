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
bands (#107), or the band diagram (#108). P8 addresses chemical-potential
root finding as described above.
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

P11 (#102) uses q(T) = B (C_K + T) / ((D_K + T) r) at each temperature
in total DPB acPhDis Seebeck, where r is the internal mass coordinate and
C_K = 300 K × C, D_K = 300 K × D. The total equals the sum of the weighted
band contributions on the same grid. P8 supplies the independent checked
chemical-potential solve; other mass/degeneracy and model limitations remain.

The P3 correction has automated identity checks. Human physicist confirmation
and the complete #71 desktop/web comparison remain outstanding.

Core version `0.1.1` identifies this P8-based P11 calculation state. P10
export-provenance metadata and P9 network-selection changes remain separate
pending work; this version does not imply human physicist confirmation.
