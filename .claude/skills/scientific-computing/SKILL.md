---
name: scientific-computing
description: Numerical and symbolic reliability for scientific code. Use when checking algebra, limits or identities with SymPy; when changing or reviewing Fermi integrals, quadrature, root finding such as the mu(T) solve, interpolation, tolerances, overflow or underflow; or when reviewing a fit objective, weights, bounds, Jacobians, multistart, uncertainty or whether parameters are identifiable. Physical model choice and derivations belong to condensed-matter-theory and seeband-transport-physics.
---

# Scientific computing

Connect a computational claim to its domain, error budget and independent evidence. A symbolic simplification, solver success flag or good fit is evidence about a calculation, not automatic scientific correctness.

## Select the relevant branch

Read only the references needed for the assigned task; combine branches when the calculation crosses them.

| Task                                                                                | Read                                                       |
| ----------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Algebra, limits, derivatives, exact identities or symbolic-to-numeric translation   | [Symbolic checks and SymPy](references/symbolic.md)        |
| Stable evaluation, roots, integration, interpolation, discretization or convergence | [Numerical reliability and SciPy](references/numerical.md) |
| Residual objectives, uncertainty, optimization or identifiability                   | [Fitting and inverse problems](references/fitting.md)      |

## Working contract

1. **Fix the claim.** Identify the requested observable, input domain, units and approved equations. For a review, distinguish inspected code, reproduced behavior and hypotheses. Preserve the assigned file scope and validation ownership.
2. **State the numerical contract.** Name parameter and residual scales, relevant singularities or boundaries, and the accuracy needed in the observable. Separate approximation/model error, discretization error, solver error and measurement uncertainty. A small residual can coexist with large parameter error in an ill-conditioned problem.
3. **Choose proportionate tools.** Use existing tooling first. SymPy is optional scratch assistance, not a runtime dependency requirement. SciPy and mpmath are optional too. Report missing tooling and use an available analytic or independent computational fallback; installation or dependency changes need their own authorization. Verify version-sensitive APIs against official documentation and record versions used.
4. **Check independently.** Use an appropriate exact case, limiting case or independently formulated calculation. Choose tolerances from the observable and its scale; preserve informative failures. Golden fixtures establish compatibility, not truth, and must not be adjusted merely to silence a failure.
5. **Report evidence.** Give equations/assumptions, inputs, commands and actual outputs needed to assess the claim, with residuals, convergence or uncertainty diagnostics as applicable. Separate performed checks from proposed checks and state remaining limitations.

## SeeBand numerical anchors

Check claims against what the code already guarantees. Paths are in `packages/seeband_core/src/seeband_core/`.

- **Fermi integrals** (`fermi_integrals.py`) are unnormalised, valid for -1 < order ≤ 4, and evaluated with fixed Gauss–Legendre and Gauss–Jacobi rules. Regimes switch at x ≤ -38 (Boltzmann, Γ(order+1)), at the edge width 8 and at the window 48. Scaled forms carry exp(-min(x, 0)) so dilute bands do not underflow. Test continuity across each switch.
- **Transport moments** (`transport.py`) use 320 fixed Legendre nodes over x ∈ [max(0, η-48), max(0, η)+48], so fit derivatives stay smooth. `math_module._band_seebeck` and `_band_lorenz` switch to the analytic degenerate form at x ≥ 40.
- **mu(T)** uses `brentq` on a normalised signed balance with an expanding bracket and a certified residual, one temperature at a time. Failure raises `ChemicalPotentialError`. Grid invariance is 1e-9 K (`packages/seeband_core/docs/chemical-potential.md`).
- **Verified fit** (`verified_fit.py`, `packages/seeband_core/docs/verified-sequential-fit.md`) is sequential `least_squares` on unweighted absolute residuals with scales S × 1e6, ρ × 1e8 and R_H × 1e10. There is no joint objective or uncertainty model yet, so stage-wise covariance is not a confidence interval.
- `parameter_status.py` reports whether each parameter was held, fixed, at a bound, not determined or not assessed, and `fit_quality.py` measures curve-to-data agreement. Use them before claiming a parameter is determined.

Preserve approved physics and existing behavior unless the assignment explicitly authorizes a change. A diagnostic finding does not authorize an algorithm migration, new solver, dependency, formula correction or golden-result update. Scientific-owner confirmation remains separate from agent review.
