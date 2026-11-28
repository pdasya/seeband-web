# Symbolic and numerical checks

Use tools to settle a specific uncertainty, not to add ceremony to a short analytic result. No package is required by this skill.

## Symbolic work

- Use exact integers/rationals until approximation is intentional. State reality, positivity and domain assumptions. Roots, logarithms and analytic continuation need branch choices.
- Preserve excluded poles and original domains after cancellation. A local numerical root is not a complete solution set; an unresolved symbolic result is not proof of no solution.
- Implement noncommuting operators with an actual algebra or a finite matrix representation. A c-number replacement is an approximation to justify.
- Verify a claimed identity by substitution/residual and independent admissible samples when useful. Floating agreement is evidence within the tested domain, not proof.
- When using SymPy, consult version-appropriate [documentation](https://docs.sympy.org/latest/). String parsing and generated/lambdified code must use trusted expressions.

## Numerical evidence

Choose the quantity that must converge before selecting a grid or tolerance: a conductivity can require much finer Fermi-surface resolution than total energy. Separate errors from discretization, Hilbert truncation, finite size, solver tolerance, stochastic sampling, physical closure and input parameters.

Use Hermitian eigensolvers for Hermitian matrices; check H−H†, eigenpair residuals and orthonormality. Degenerate eigenvectors may rotate arbitrarily; compare projectors or subspaces instead of vector components. A condition number or spectral gap can make a small residual compatible with a large inferred error.

For response functions distinguish η broadening from a physically derived scattering rate and examine convergence jointly with size/grid and ω. For time evolution check appropriate norm/trace, conservation and cutoff dependence. Pointwise positivity checks on a density matrix do not apply to a Wigner quasidistribution.

For Monte Carlo, estimate autocorrelation and effective sample size; a seed reproduces a stream only within a specified algorithm/environment. Burn-in, independent runs and finite-size extrapolation address different issues.

Report the model, versions, parameters, actual checks and tolerance relevant to the observable. Do not report a proposed calculation as executed. SciPy is an optional numerical backend; verify current [API contracts](https://docs.scipy.org/doc/scipy/) before use. QuTiP is useful for finite quantum models but not a generic large-lattice solver.

## Compact exact example

For σ=[[a,b],[-b,a]],

\[
\rho=\sigma^{-1}=\frac{1}{a^2+b^2}
\begin{pmatrix}a&-b\\b&a\end{pmatrix},\qquad a^2+b^2\ne0.
\]

Multiply the matrices to verify the identity. A Hall sign follows the declared placement of tensor entries; it is not fixed by writing an unsigned scalar formula. Distinguish the resistivity element from the measured Hall-voltage geometry.
