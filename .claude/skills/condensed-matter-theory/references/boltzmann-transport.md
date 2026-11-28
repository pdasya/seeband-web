# Boltzmann transport

Use for quasiparticle kinetics after identifying a regime where band populations suffice. If interband coherence, tunneling or spatial quantum corrections are central, start with [Wigner transport](wigner-transport.md).

## Fix variables and physical assumptions

In SI, signed carrier charge q gives ℏ k-dot=q(E+v×B) for a simple band without Berry corrections; v=(1/ℏ)∇k ε. With kinetic momentum p=ℏk, p-dot is force. Never carry the same force derivative between p and k without its ℏ factor.

Specify dimension, dispersion, chemical potential, equilibrium distribution, degeneracy and scattering mechanism. Use ∫dᵈk/(2π)ᵈ per physical d-volume with any spin/valley multiplicity included exactly once. A 2D sheet conductivity and 3D conductivity have different units; conversion needs physical thickness.

The relaxation-time approximation is a collision model, not a consequence of linear response. Distinguish transport relaxation from quasiparticle lifetime and phase-coherence time. Momentum-conserving collisions alone do not always relax current; conservation laws and lattice/Umklapp physics determine this.

## Longitudinal zero-field anchor

For uniform weak E, well-defined quasiparticles and scalar τₙ(k),

\[
\delta f_{n\mathbf k}=q\tau_{n\mathbf k}
\mathbf E\cdot\mathbf v_{n\mathbf k}(-\partial_\epsilon f_0),
\qquad
\sigma_{ij}=q^2\sum_n\int\frac{d^dk}{(2\pi)^d}
\tau_{n\mathbf k}v_{ni}v_{nj}(-\partial_\epsilon f_0).
\]

The band sum here includes every counted internal state; add an external degeneracy only if those states were omitted. Derive the sign of δf from the stated signed q. This anchor excludes Berry, magnetic-field, side-jump and skew-scattering corrections.

For an isotropic parabolic dispersion and constant τ, integration by parts gives σij=δij nq²τ/m when boundary terms vanish. Check at finite T or with the proper Fermi-surface measure at T=0. A truncated band or bounded momentum domain needs its own boundary analysis.

## Multiband, magnetic and thermal problems

- Sum conductivity tensors of parallel channels, then invert the full tensor to obtain resistivity. In general ρij is not 1/σij. Specify the placement and sign of Hall entries before interpreting carrier sign.
- A multiband fit requires identifiable parameters and a physical model. Hall sign alone does not determine a unique carrier density or number of bands.
- State assumptions behind a weak-B expansion and compare ωcτ with unity. Berry curvature changes equations of motion and phase-space measure; derive those changes consistently with band projection.
- Heat current uses ε−μ and couples charge and thermal response. Specify the measured condition (for example open circuit) before extracting thermal conductivity. Do not equate electronic, lattice and total κ.

For SeeBand's parabolic-band conventions, scattering exponents and executable limit checks, use the project skill `seeband-transport-physics`.

For numerical integration resolve the Fermi window or surface, verify grid convergence and distinguish integration error from the assumed scattering model. See [checks](symbolic-and-numerical-checks.md).
