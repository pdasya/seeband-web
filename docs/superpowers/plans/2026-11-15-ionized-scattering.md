# Ionized scattering implementation plan

> **For agentic workers:** Execute bounded tasks in the current session, following repository validation and review ownership.

**Goal:** Replace public acPhDis with ionized impurity power-law transport for SPB and DPB.
**Architecture:** Explicit immutable scattering parameters feed common transport moments. Registry descriptions drive API and UI; historical low-level paths remain reproducible.
**Tech Stack:** Existing NumPy/SciPy Python core, FastAPI, React/TypeScript.
**Spec:** ../specs/2026-11-15-ionized-scattering-design.md

## Global constraints

- tau(E) proportional to E^(3/2), lambda=2; no screening or mutable global lambda.
- Preserve acPh/dis outputs and historical captures. Do not mutate measurements.
- No silent legacy fallback; no neural estimate trained for another mechanism.
- Parent owns validation; no push or merge requested.

## Review focus

- Hall uses second lifetime moment, not a longitudinal shifted integral.
- Interleaved mechanisms and S-only requests keep independent lambda.
- Old acPhDis sessions fail validation instead of changing mechanism silently.
- Estimates and asynchronous answers retain scattering identity.
- Extreme reduced potentials preserve numerical precision and honest failure.

## Tasks

- [x] Core worker: write failing independent physics and integration tests; implement explicit mechanisms and lambda-aware moments; connect verified fitting and all curves; update public descriptions and focused tests. SPB guess accepts optional scattering; `ionized` legacy rejects explicitly.
- [x] Parent: API guess carries optional scattering and refuses DPB ionized neural estimates; web selection, method restrictions, guess identity and session compatibility tests first, then minimal implementation.
- [x] Parent: regenerate API contract/types; update current docs, version/lock metadata and public regression tests without rewriting historical evidence.
- [x] Physics reviewer: independent formulas, mass/sign/scattering limits; numerics reviewer: high-order moments, derivatives and fit consistency; general reviewer: API/UI/session integration.
- [x] Parent: run focused checks during integration, then pnpm check once on final revision; repair and rerun only affected checks. Restart local services and verify the new selector and API.

## Validation evidence

- Full `pnpm check` reached an obsolete mock-version expectation; the corrected API-client suite passed all 61 tests. Lint and TypeScript checks passed.
- Web: 564 unit tests, seven production-build checks, and 408 browser tests passed on the broad run. Four obsolete browser expectations were updated for S-only scattering, removed C/D and guess identity; all four then passed. The 22 environment-gated browser cases remained skipped.
- Full Python run: 4,060 passed and five obsolete public-interface expectations failed. Updated those expectations for the retired mixed mechanism and S-only scattering. The complete affected warning group, request-validation group and new ionized tests then passed: 152 tests. No formula, objective, tolerance or measurement was changed to resolve those failures.
- Final Ruff lint/format, mypy, generated OpenAPI comparison and diff whitespace checks passed. Physics, numerics and integration reviews have no remaining findings. Live core 0.3.0 responds through the local web proxy; ionized SPB/DPB calculations and early Legacy rejection were checked.
