# P13 positive DPB weights Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. The owner has authorized implementation and fresh reviews; do not merge.

**Goal:** Remove negative longitudinal DPB weights while retaining carrier signs and fitting within the initial carrier branch.

**Architecture:** Correct shared math kernels and intersect DPB fit mass bounds with the initial branch. Keep the public signed mass representation and density solver.

**Tech Stack:** Python, NumPy, SciPy, pytest; existing TypeScript clients.

**Spec:** `docs/superpowers/specs/2026-11-15-p13-positive-dpb-weights-design.md`

## Global Constraints

- No P18 expansion or API migration; no merge.
- Preserve r=R/N, signed occupations and density; change longitudinal weights only.
- Fix each fit's sign from its initial mass; exclude zero without arbitrary floors.
- Preserve objectives, tolerances and independent physical release gates.
- Parent owns full validation; workers run focused checks only.

## Review Focus

- Negative masses must preserve own-band thermopower and Hall signs.
- Same-type coincident bands must add instead of cancel in every scattering mode.
- Nonunit degeneracy must retain the existing public/internal mapping and P6 warning.
- Zero, empty branch bounds and invalid starts must fail explicitly.
- Positive-branch regressions and updated references must remain traceable.

## Task 1: Shared transport and fit branch correction

Files: `packages/seeband_core/src/seeband_core/{math_module,fit_module}.py`, focused core tests including `test_dpb_acphdis_weight.py`.

- [x] Add physical regression tests and branch-bound tests; run against old code and record failures.
- [x] Use positive transport weights in total and per-band kernels; retain Hall signs.
- [x] Intersect mass bounds with the initial signed branch in all DPB fitting modes.
- [x] Run focused tests and document observed compatibility changes.

## Task 2: Integration and validation

Files: conventions, changelog, known-issue registry/consumers, version metadata and affected regression fixtures.

- [x] Update docs, issue flags, version and justified references from actual runs.
- [x] Obtain fresh read-only general and physics reviews with relevant skills.
- [x] Resolve substantiated findings and run affected checks.
- [x] Run `pnpm check` once on the final revision and report remaining limitations.

No push, PR creation or merge is required by this implementation request.

## Completion evidence

- Worker focused RED/GREEN: 24 failed before the transport correction; 164 passed
  after it. Review-fix focused set: 165 passed, including six physical registry
  fit recoveries and implicit/tighter branch-bound diagnostics.
- Fresh physics and general reviews completed. Two findings (bound diagnostics
  and iterative-degeneracy documentation) were resolved and re-reviewed.
- Repository lint/format and workspace typechecks passed. API client 61, UI 17,
  web unit 534, build 7 and browser 404 passed; 22 browser cases are skipped.
- Python full run: 4091 passed, 25 failed. Twenty-four failures were sandbox
  loopback EPERM and pass when rerun with local-server access. One independent
  manual-loop test still used historical cross-zero bounds; its reference now
  applies the approved positive branch. Both manual-loop parameter cases pass
  without changing comparison tolerances. All 4116 cases are accounted for.
- Initial `pnpm check` was stopped at the sandbox server restriction; its remaining
  constituent commands were completed separately, with affected checks rerun
  after corrections. No redundant full suite was repeated.
- Wheel/sdist 0.1.4 built and wheel metadata verified. No commits, push, PR or merge.
