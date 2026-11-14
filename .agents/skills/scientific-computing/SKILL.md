---
name: scientific-computing
description: Use when verifying symbolic expressions with SymPy, assessing numerical stability and solvers with SciPy, or interpreting inverse problems and fits. Applies to scientific calculations and reviews; physical model selection and derivations remain with condensed-matter-theory.
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

Preserve approved physics and existing behavior unless the assignment explicitly authorizes a change. A diagnostic finding does not authorize an algorithm migration, new solver, dependency, formula correction or golden-result update. Scientific-owner confirmation remains separate from agent review.
