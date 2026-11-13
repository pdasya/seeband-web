# P5 DPB convergence implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development, with repository role routing and one final validation owner.

**Goal:** Prevent premature mixed-scattering DPB convergence and division-by-zero/NaN false success.

**Architecture:** Repair both existing loops in the core and their shared change/accuracy checks. Keep the finite nonzero relative-change convention and the existing iteration budget; broader stopping-rule redesign belongs to #176.

**Tech stack:** Python, NumPy, SciPy, pytest; generated FastAPI descriptions and TypeScript client.

**Spec:** [P5 #84](https://github.com/pdasya/seeband-web/issues/84), including NUM-2 and INV-4. Base is main at 00c1d3e; P4/P12 is a separate unmerged PR.

## Constraints and review focus

- Preserve original desktop captures and unrelated physical formulas, including the separate #102 limitation.
- Nonfinite changes cannot mean convergence. Unchanged zero is zero change; departure from zero is not converged.
- Test both mixed-scattering groups independently, both fit modes, iteration limits and zero initial parameters.
- Numerical changes require separate corrected regression expectations, changelog and human physicist confirmation. Parity #71 remains pending.

## Tasks

- [x] Worker: reproduce both group-order early exits and zero/nonfinite false convergence with failing tests, including a real-example reproduction.
- [x] Worker: repair loop conjunction and safe relative changes, update focused tests and remove only the fixed early-stop flag.
- [x] Worker: capture corrected regression expectations separately; record iterations/status for three examples and both DPB modes.
- [x] Parent: update public warnings, API contract and affected integration expectations; document numerical differences and remaining gates.
- [x] Physics reviewer: independently review numerical contract and final behavior; general reviewer: review integration once.
- [x] Parent: run focused integration checks, then one final `pnpm check`; rerun affected checks only after any fix.

## Evidence

- Before the fix, controlled regressions reported 10 failures, including both group-order early exits, zero division and nonfinite false convergence. A separate baseline run reproduced both real-example failures (two iterations instead of three).
- Focused core tests: 725 passed; after expanding zero-initial coverage, the convergence file passed all 42 cases. API descriptions: 26 passed. Frontend result-summary tests: 28 passed.
- All six recorded mixed-scattering fits now complete three iterations without exhausting their original budgets. The Hall budget remains 20; collapsed-band warnings remain on the affected example.
- Final `pnpm check` passed: 3208 Python tests, 22 inherited numerical warnings, and all required lint/type/client/UI/browser checks. Logs are outside the checkout at `/private/tmp/p5-check.log`.
- General and physics reviewers found no actionable defects. Physics review independently recomputed all six histories and checked scale invariance. Human physicist confirmation and #71 remain pending.
