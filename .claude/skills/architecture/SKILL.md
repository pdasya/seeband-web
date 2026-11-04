---
name: architecture
description: Boundaries and invariants of SeeBand Web. Use when adding or moving a feature, model, endpoint, package or dependency, when deciding where logic belongs between `apps/web`, `apps/api` and `seeband_core`, when changing how measurements, LLM calls or fit processes are handled, or when a change could alter calculated numbers.
---

# SeeBand Web architecture

Calculations run only on the server. The browser shows data and results.

## Where code belongs

| Location                | Holds                                                  | Must not hold                                                 |
| ----------------------- | ------------------------------------------------------ | ------------------------------------------------------------- |
| `packages/seeband_core` | formulas, fits, parsing, interpolation, model registry | Qt, TensorFlow, FastAPI, HTTP concerns, input mutation        |
| `apps/api`              | routes, validation, process management, LLM gateway    | formulas, stored measurements                                 |
| `apps/web`              | forms from model descriptions, charts, session state   | formulas, fit logic, API keys, model-specific parameter lists |
| `apps/site`             | static public pages                                    | application logic, Plotly, Pyodide                            |
| `packages/ui`           | tokens, shared header, language switch                 | application state                                             |
| `packages/api-client`   | types generated from OpenAPI                           | hand-written API types                                        |

## Rules

- **New models go through the registry.** A typical model must need no client changes.
- **Scale conversion stays in one module of the core.** The API and client use core units and model descriptions.
- **Measurements are not stored or logged.** Logs hold method, route, status and duration, never request bodies.
- **LLM keys stay on the server.** All numbers in a summary come from the core, and the LLM does not recalculate them. Raw points are sent only with explicit consent.
- **CPU-heavy fits run in a separate process that can be killed.** `async` does not make them parallel, and `ProcessPoolExecutor` cannot interrupt a running task.
- **The API keeps no state between calls.**

## Changing numbers

The first stage is an exact port of the desktop application.

- Numbers may change only with updated golden results in the same pull request.
- A physics change belongs to the Physics fixes milestone. Write a test for the physical limit first, then fix, update golden results, record it in the changelog, and get a physicist's confirmation.
- Known errors stay flagged through the known-issue registry until they are fixed. Never hide them, and never fix them inside unrelated work.

If a task seems to need breaking one of these rules, stop and raise it instead of working around it.
