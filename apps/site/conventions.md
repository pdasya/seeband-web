# Calculation conventions

## SPB Hall

For the enabled SPB Hall mode, `x = sign(m) μ(T)/T`, where μ(T) conserves
the carrier density set by E_F at zero temperature. The signed mass m is in
units of mₑ: positive for electrons and negative for holes. A point with signed
reduced potential `x > 700` is outside the supported integral range and returns
NaN. For acoustic scattering,

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
masses: entering m_d,2/m_d,1 would count N twice. For R > 0, the transport
weight N/R holds for λ = 0 acoustic deformation-potential scattering with
the same deformation potential and elastic constant in both bands,
isotropic valleys whose band mass serves for both density and conduction,
and no inter-valley or inter-band scattering. Under these assumptions the
positive longitudinal mass/valley prefactor is Nᵢ/|mᵢ|; band occupations
and scattering factors still enter the conductivity. This is not a formula
for the entire conductivity independent of band filling. Other scattering
mechanisms need different transport factors.

For R < 0 the signed S-only transport weight N/R is the open #104. In
this S-only expression, cancellation at R = −N requires equal band occupation
integrals, as for coincident band edges (E_g = 0); it is not a general result
for negative R or for other transport weights.

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

The existing total-Seebeck grid-weighting error (#102) is separate: on a
multi-point grid the total can still disagree with the sum of the corrected
band contributions. Its warning remains visible. Other known model-domain
and numerical limitations remain listed in the core's known-issues document.

The P3 correction has automated identity checks. Human physicist confirmation
and the complete #71 desktop/web comparison remain outstanding.
