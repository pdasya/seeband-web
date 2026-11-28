# Magnetism

## Model conventions

Declare localized versus itinerant degrees of freedom, spin length, dimension, exchange range, anisotropy, field and ensemble. With dimensionless spin operators and ℏ=1,

\[
H=J\sum_{\langle ij\rangle}\mathbf S_i\cdot\mathbf S_j
-\sum_i\boldsymbol\mu_i\cdot\mathbf B,
\]

where each bond is counted once, J>0 favors antiferromagnetic alignment. A convention with −J reverses that identification. Define μ in terms of S and its signed gyromagnetic ratio: electron spin magnetic moment is antiparallel to spin angular momentum. Do not substitute S=σ for spin one half; S=σ/2 in these units. If dimensional angular-momentum operators are used, track their ℏ and the corresponding coupling units.

Identify the measured susceptibility: derivative with respect to B or H, total or density, per mole or formula unit, SI or Gaussian. μ₀, Avogadro factors and demagnetization corrections depend on those definitions. Thermodynamic derivatives follow from the same field coupling and normalization.

## Benchmark: Heisenberg dimer

For H=J S₁·S₂, S₁=S₂=1/2 and ℏ=1,

\[
H=\frac J2[S_{\rm tot}(S_{\rm tot}+1)-3/2],
\quad E_s=-3J/4\ (1),\qquad E_t=J/4\ (3).
\]

Parentheses give degeneracies. Check this with an explicit four-state matrix if manipulating spin conventions. J>0 has a singlet ground state; J<0 has a triplet. The high-temperature zero-field partition function tends to four, and mean interaction energy tends to zero.

## Choose a justified approximation

- Mean field: state decoupling, coordination, candidate ordering vector and spin convention. A self-consistency instability is a mean-field scale; compare competing states and fluctuations before interpreting it as a transition.
- Curie–Weiss: specify the high-T regime, moment and susceptibility baseline. The Weiss temperature does not by itself equal an ordering temperature or uniquely identify a microscopic exchange network.
- Spin wave: specify ordered reference state, sublattice rotations and Holstein–Primakoff order. For antiferromagnets or pairing terms use the appropriate bosonic Bogoliubov metric, not ordinary Hermitian diagonalization. Examine stability and magnon occupation relative to S.
- Itinerant models: identify interaction decoupling and susceptibility entering a Stoner/RPA criterion. Separate bare-band response from an interacting observable and avoid inferring an exact critical point from an approximate denominator.

## Dimensionality and order

The infinite 1D/2D isotropic finite-range Heisenberg model cannot develop spontaneous ferro- or antiferromagnetic long-range order at nonzero temperature under the Mermin–Wagner assumptions. A finite mean-field Tc does not evade this. State continuous symmetry, range, equilibrium, thermodynamic limit and symmetry-breaking-field order of limits. Anisotropy, interlayer coupling, long-range interactions or a driven setting require their own analysis.

Absence of conventional long-range order is not a universal absence of all transitions: quasi-long-range order/BKT requires its own symmetry and defect structure; it cannot be assigned automatically to every 2D spin model. Finite samples can have a large correlation length without bulk spontaneous order.

Source: [Mermin and Wagner, PRL 17, 1133 (1966)](https://doi.org/10.1103/PhysRevLett.17.1133), with its [erratum](https://doi.org/10.1103/PhysRevLett.17.1307). For finite-size numerical evidence, separate equilibration, sampling correlation, finite-size drift and extrapolation uncertainty.
