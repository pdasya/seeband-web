# Wigner transport

## Choose the branch and object

Distinguish electronic/spin one-particle density-matrix transport, phonon heat transport, and energy-resolved Keldysh/NEGF kinetics. An equal-time Wigner matrix is not a spectral Green function; integrating an interacting theory to equal time requires a closure. Name which object and approximation the task uses.

For a continuum equal-time density matrix, adopt this explicit convention in d dimensions unless the task specifies another:

\[
W_{ab}(R,p,t)=\int d^ds\,e^{-ip\cdot s/\hbar}
\rho_{ab}(R+s/2,R-s/2,t),\qquad
n(R)=\int\frac{d^dp}{(2\pi\hbar)^d}\operatorname{tr}W.
\]

Here ρab=⟨ψ†b(r₂)ψa(r₁)⟩ is the one-body density matrix; its trace integrates to particle number rather than necessarily one. Moving (2πℏ)⁻ᵈ into W is also valid, but change inverse transform, density and observable measures together. Define lattice/Bloch analogues separately, with cell/orbital positions and Brillouin-zone measures. W is a quasidistribution: pointwise negativity alone does not invalidate it or justify clipping it.

## Closed one-body evolution and the gradient expansion

With H the Weyl symbol of the Hamiltonian, canonical variables (R,p), a fixed internal basis and no collision term,

\[
i\hbar\partial_tW=H\star W-W\star H,\qquad
A\star B=A\exp\!\left[\frac{i\hbar}{2}
(\overleftarrow\nabla_R\cdot\overrightarrow\nabla_p
-\overleftarrow\nabla_p\cdot\overrightarrow\nabla_R)\right]B.
\]

Retaining the first phase-space gradient term gives

\[
\partial_tW+\frac{i}{\hbar}[H,W]
+\frac12\sum_i\{\partial_{p_i}H,\partial_{R_i}W\}_+
-\frac12\sum_i\{\partial_{R_i}H,\partial_{p_i}W\}_+
=I_{\rm coll}[W].
\]

The right side is zero for the closed problem; a nonzero collision model is an additional approximation. Braces are matrix anticommutators, not scalar Poisson brackets. Justify truncation using variation scales and resolution of W as well as H. Count orders in the star product before dividing by ℏ; matrix commutators can leave even star orders, whereas scalar commutators cancel them. Do not label every matrix remainder as O(ℏ²).

Checks: H=p²/2m+V gives ∂tW+(p/m)·∇RW−∇V·∇pW=0 at this order. Scalar quadratic Hamiltonians have no higher Moyal correction. For a smooth 1D scalar potential the first correction on the right is −ℏ² V'''∂p³W/24. For spatially uniform H=d·σ and W=(fI+s·σ)/2, coherent evolution gives s-dot=2d×s/ℏ; it survives zero gradients.

## Fields, basis and closure

- **Electromagnetic gauge:** ordinary canonical W is gauge dependent. Use a gauge-covariant transform (an appropriate link between endpoints) and kinetic variables when required. Merely replacing p by p−qA in the canonical equation is insufficient in general. Recover q(E+v×B) in the scalar semiclassical SI limit. This is distinct from gauge freedom of band eigenvectors. See [Iafrate et al.](https://arxiv.org/abs/1708.01439).
- **Changing internal basis:** a varying U(R,p,t) produces connection and gradient corrections. Consistent Weyl transformations use star products, including the order-by-order transformed Hamiltonian, state and observables. Bare U†WU followed by ordinary derivatives is only a zeroth-order step. Retain a degenerate block near crossings; do not divide by a vanishing band gap. See [Wickles and Belzig](https://arxiv.org/abs/1209.4933).
- **Projection to Boltzmann:** small gradients alone do not suppress coherences. Assess gap versus mixing and drive, initial preparation, dephasing and the measured observable. Controlled elimination can leave Berry/current corrections even when only populations remain.
- **Collisions:** define the bath/disorder/interaction model and closure, locality and Markov assumptions. Population relaxation and dephasing need not share τ. Test conservation moments appropriate to that model; a fixed-equilibrium RTA generally needs modification to conserve local particle number. Do not claim an arbitrary relaxation matrix is conserving or completely positive.
- **Boundaries:** specify initial density matrix and open/closed/contact conditions. Quantum phase-space inflow is not always classical inflow. State what flux or integrated continuity law is checked.

## Phonon Wigner heat transport

Use a mode-space occupation/coherence matrix, phonon frequencies, velocity matrix, Bose statistics and a defined scattering/linewidth convention. It is a different object from an electronic Fermi distribution. The Wigner formulation of Simoncelli, Marzari and Mauri connects population and coherence contributions to lattice heat transport and discusses the relationship with Peierls–Boltzmann and Allen–Feldman descriptions. Bloch phase conventions, cell choice and off-diagonal velocity elements matter for a consistent conductivity. [PRX 12, 041011 (2022)](https://doi.org/10.1103/PhysRevX.12.041011).

Before deriving a quantitative κ formula, consult that paper's definitions of current, normalization and linewidths. Distinguish mode spacing from linewidth and do not drop off-diagonal elements solely because real-space temperature gradients are weak. Specify κP and κC only in the chosen formulation; compare the total observable under a consistent basis change. Phonon data generation and full anharmonic scattering solvers are outside this reference.

## Completion evidence

State the transform, basis, measure, expansion order, closure and observable. Check a scalar classical limit and, for matrix transport, a coherent or basis-consistency limit. For computed solutions check integrated particle/energy balance as applicable, resolution in both R and p, boundary flux and cutoff dependence. A small equation residual alone does not validate projection or collision physics.
