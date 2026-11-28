# Hamiltonians and symmetry

Use for model construction, basis changes and effective Hamiltonians. For response or kinetics, continue to the relevant transport reference.

## Specify the object before manipulating it

Record the degrees of freedom and basis order: site, orbital, spin, sublattice, particle/hole. Distinguish a one-body matrix h from a many-body operator H and a self-consistent mean-field Hamiltonian. Define creation/annihilation (anti)commutators, occupancy constraints, chemical potential and the energy zero.

For lattice sums specify whether bonds are directed or counted once. Include the Hermitian conjugate only when the sum has not already included it. Track lattice constants and whether k is dimensional. Declare the Fourier transform before mapping hopping amplitudes to h(k).

For position- and momentum-dependent operators define ordering; a classical-looking expression is not automatically its Weyl symbol. Wigner transport needs that symbol or explicit ordering corrections.

## Useful checks

- Hermiticity at admissible real parameter values; conjugate complex hopping amplitudes explicitly.
- Unitary symmetry: transform both h and momentum. Antiunitary symmetry: include complex conjugation and its action on spin, not just a unitary matrix.
- Conserved Q: test [H,Q]=0 with the actual algebra. Distinguish exact, approximate and spontaneously broken symmetries.
- Basis change: transform states, observables and Hamiltonian consistently. A k-dependent transformation changes derivative operators and can introduce connections.
- Effective models: name the retained subspace, separation of energy scales, eliminated couplings and perturbative order. Check near degeneracies separately.
- BdG: declare the Nambu basis, particle-hole redundancy, factors of one half and constant shifts. Double counting is not a physical degeneracy.

## Benchmark: a two-component Hamiltonian

For h(k)=d₀(k)I+d(k)·σ with real d₀,d at each k,

\[
E_\pm=d_0\pm |d|,\qquad
P_\pm=\tfrac12(I\pm\hat d\cdot\sigma),\quad |d|\ne0.
\]

Check the trace, determinant, hP±=E±P± and completeness of the projectors. At d=0 the eigenspace is degenerate and the direction d-hat is undefined; choose a subspace treatment rather than differentiating singular eigenvectors. Eigenvalues alone do not determine Berry curvature or a topological invariant: eigenvectors/projectors and global structure matter.

For spin exchange, use the [dimer benchmark](magnetism.md). For gradient-dependent basis transformations, read [Wigner transport](wigner-transport.md).
