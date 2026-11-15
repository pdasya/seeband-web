# P19 verified sequential fitting Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development with the repository's role and concurrency limits. The owner authorized implementation; do not merge.

**Goal:** Correct false numerical convergence generally, making verified fitting the default with explicit legacy reproduction.

**Architecture:** Add a separate numerical engine sharing physical kernels, dispatch at the model interface, and carry algorithm/diagnostics through API, session and exports. Preserve legacy internals.

**Tech Stack:** Existing NumPy, SciPy, Python dataclasses/Pydantic, TypeScript/React and generated OpenAPI.

**Spec:** `docs/superpowers/specs/2026-11-15-p19-verified-sequential-design.md`

## Global Constraints

- Preserve staged objectives, measurements, bounds, held values, P13 physics and P8 density certification.
- No sample-specific logic, mass floors, new dependencies, joint objective or implicit legacy fallback.
- Verified coordinates use public R and one r=R/N conversion; legacy remains explicit and unchanged.
- One writer per file; parent owns integration and full validation; workers run focused checks.

## Review Focus

- Tiny positive amplitudes must reach independently known conditional optima.
- A final rho update must not leave an unchecked S objective.
- Held variables, zeros, nonunit degeneracy and active constraints must retain their meaning.
- Numerical convergence must not claim physical adequacy or unique parameters.
- Algorithm identity must survive API, cache/session and exports; historical tests explicitly choose legacy.

## Task 1: Core numerical engine

Files: model_interface.py, band_models.py, new verified_fit.py and new focused tests.

- [x] Write and run failing synthetic stage and outer-loop/P6 tests.
- [x] Implement exact amplitude profiling, scaled admissible stages, consistency audits and finite recovery/budgets.
- [x] Dispatch verified by default, explicit legacy unchanged, and return typed algorithm/diagnostics.
- [x] Run all applicable mode/scattering/branch/held/bound focused tests, including measured residual agreement.

## Task 2: API and client integration

Files: API fit request/response, web selection/request/session/settings/status/export and focused integration tests.

- [x] Add validated explicit algorithm selection and typed diagnostic serialization.
- [x] Keep legacy selectable and persisted, with unknown provenance for old results.
- [x] Show numerical/consistency/residual/identifiability information without claiming physical acceptance.
- [x] Regenerate client types; test default/legacy requests, round trips, cache identity and exports.

## Task 3: Integration, evidence and review

- [x] Pin historical estimator tests explicitly to legacy and add separate verified regressions.
- [x] Update core version, conventions, changelog and known-issue behavior by algorithm.
- [x] Record aggregate before/after synthetic, SiP and D1 evidence; retain original fixtures.
- [x] Obtain fresh general, numerical and physical reviews in distinct scopes; resolve substantiated findings.
- [x] Complete required checks, including affected reruns after fixes; final Python continuation, exact-cache validation and generated contract checks completed.

No merge. Publication is a separate instruction.
