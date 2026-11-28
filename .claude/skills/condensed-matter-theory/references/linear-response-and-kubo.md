# Linear response and Kubo

## Declare the response convention

Identify source f and observable A, including whether A itself depends on f. One consistent convention is

\[
H'(t)=-f(t)B,\qquad
\delta\langle A(t)\rangle=\int dt'\,\chi_{AB}(t-t')f(t'),
\qquad
\chi_{AB}(t)=\frac{i}{\hbar}\theta(t)\langle[A(t),B(0)]\rangle_0.
\]

This plus-i definition follows from the stated minus-source coupling. Many references instead call −iθ⟨[A,B]⟩/ℏ the retarded Green function. Translate the coupling and response together; do not change one sign in isolation. An explicit source derivative of A supplies an additional contact response.

Use f(t) proportional to exp(−iωt) and χ(ω)=∫dt exp(iωt)χ(t) unless the task uses another convention. State equilibrium density matrix, total versus density operators and volume/area normalization. Angular frequency ω is not energy ℏω or cyclic frequency ν.

## Electrical conductivity

Derive the physical current from the actual coupling to A and scalar potential. In a continuum minimal-coupling model or a Peierls-coupled lattice, differentiation generates both the current vertex and applicable contact/diamagnetic terms. A truncated Dirac-like Hamiltonian needs consistent regularization and remote-band treatment where relevant; absence of an explicit A² term is not a universal permission to omit the physical contact contribution.

Define the complete current-density kernel K by δj=KδA. In temporal gauge, with the Fourier convention above, E=iωA and the retarded prescription gives σ=K/[i(ω+i0⁺)]. This is a relation between defined kernels, not a substitute for deriving K. Use consistent total-current versus density factors throughout.

For heat, thermoelectric, Hall or orbital response, identify energy/heat currents and applicable magnetization-current subtractions. Charge-current formulas cannot simply be relabeled as thermal conductivity.

## Derive, then test

1. Write source coupling and source-dependent observable; identify contact terms.
2. Obtain a Lehmann, Matsubara or real-time representation suited to the model. Track occupation differences, degeneracy and factors of ℏ.
3. For Matsubara calculations distinguish bosonic transfer from fermionic internal frequencies. State whether continuation uses energy iΩ→ℏω+i0⁺ or frequency iωₙ→ω+i0⁺.
4. State q→0, ω→0, size→∞ and scattering/broadening limits in the physical order. The uniform transport limit and static equilibrium limit can differ. A closed finite system has discrete spectral weight; plotting it with finite η does not establish irreversible DC transport.
5. Check causality, appropriate tensor symmetries and a known limit. Use Ward identities and sum rules when applicable, with their assumptions. Distinguish exact, conserving and bare-bubble approximations; adding a lifetime may require compatible vertex corrections.

## Simple anchor

For a spatially uniform isotropic parabolic band with momentum-relaxation time τ, density n and charge magnitude e,

\[
\sigma(\omega)=\frac{ne^2\tau}{m(1-i\omega\tau)}.
\]

Check DC σ=ne²τ/m and nonnegative dissipative longitudinal response. The clean limit is distributional, with a zero-frequency Drude contribution; do not replace it by a finite DC number. Different conventions for Drude weight move factors of π between its definition and δ(ω).

Derivations should cite an actual consulted equation when prefactors are borrowed. See [sources](sources.md) for linear-response lecture notes and [Boltzmann transport](boltzmann-transport.md) for an independent Drude check.
