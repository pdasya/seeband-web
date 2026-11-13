# P6 DPB S-only degeneracy implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development with repository role routing and one final validation owner.

**Goal:** Make the DPB S-only fitting objective and drawn curve use the same mass convention for nonunit degeneracy.

**Architecture:** Public signed parameter R = m₂/|m₁| (`m_eff`) remains in its existing mass-ratio units. Both fitting and calculation boundaries pass r = R/N to the low-level model, with N = N₂/N₁. No transport or chemical-potential formulas change.

**Tech stack:** Python, NumPy, SciPy, pytest; generated FastAPI contract and TypeScript client.

**Spec:** [P6 #85](https://github.com/pdasya/seeband-web/issues/85). Base is main at 00c1d3e, independent of the unmerged P4/P5 PRs.

## Constraints and review focus

- Write failing nonunit-N objective/redraw and physical-limit tests first; preserve N = 1 results.
- Keep starts, bounds, returned parameters and covariance in public R units.
- Exercise N = 3, fractional ratios and equivalent N₁/N₂ pairs; preserve request inputs.
- Keep historical desktop captures, iterative-mode degeneracy warnings and unrelated formula/diagram issues.
- Explain poor real-data RMSE separately from objective/redraw consistency. Convergence does not establish fit quality or identifiability.
- Human physicist confirmation and parity #71 remain pending.

## Tasks

- [x] Worker: reproduce the fit/redraw mismatch and N = 3 physical weighting in failing tests.
- [x] Worker: align the S-only fitting boundary, add synthetic recovery/regression expectations, investigate example residuals, and remove only the repaired S-only flag.
- [x] Parent: document the mass convention and its limits, remove obsolete public warning text, regenerate the API contract, and update affected integration expectations.
- [x] Physics reviewer: verify independent density/transport weighting and final numerical evidence; general reviewer: review integration once.
- [x] Parent: run focused integration checks and final `pnpm check`; fix and rerun affected checks if needed.

## Validation evidence

- Before the fix, six regressions failed and three unit-N checks passed. The N = 3 objective/redraw discrepancy was 120.317174 µV/K at the documented reference parameters.
- Focused P6 and known-issue tests: 128 passed. Historical S-only golden replay: six passed. API model tests: 27 passed.
- Independent Fermi quadrature and bracketed charge-root tests verify density/transport weights without the core integral table or fsolve. Synthetic recovery is explicitly model-generated evidence.
- Final `pnpm check` passed: 3183 Python tests (31 solver warnings), 381 browser scenarios passed and 21 skipped, plus lint, type checks, unit/client/UI tests, Ruff and mypy. Full log: `/private/tmp/p6-check.log`, outside the checkout.
- General and physics reviewers found no actionable defects. The partially unresolved #85 iterative warning, human physicist confirmation, and #71 parity remain open.
- The measured-data residual investigation and the unreproduced historical approximately 32 µV/K case are documented in `packages/seeband_core/docs/dpb-s-degeneracy.md`.
