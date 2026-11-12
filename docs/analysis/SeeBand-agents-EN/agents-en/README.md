# SeeBand agent instruction pack

This package contains eight English Markdown profiles with front matter matching the style of the project's existing .claude/agents files. They are prepared profiles and portable instructions, not agents installed in the project. The original restriction against changing the project remains in place. Do not overwrite the existing physics-reviewer profile; the new names are intentionally distinct. No execution model is pinned.

This is the English translation of the agent instructions and launch guide. The original concept report and evidence appendix remain in Russian and are included under reference-ru/ for context.

## Use now

Provide the selected agent with its profile, reference-ru/SeeBand-concept.md, and reference-ru/evidence.md. Specify the current commit, scope, and read-only mode. Three temporary agents, physics/performance/ux, participated in the original review; they are not persistent background processes.

## Install later

After a separate instruction to configure agents, selected profiles can be added to the project's .claude/agents/ directory after checking the environment's supported tools and rules. This has not been done. In another agent environment, use the profile body as task/system instructions; the front matter is not a universal executable format.

The tools field matches the repository convention. Bash is not technically read-only; the read-only restriction is behavioral and must also be enforced by the host's permissions when available.

## Ready-to-use review assignment

> Use review-coordinator.md. Work read-only at commit <SHA>. Read the concept report and evidence appendix. Build a model/mode/scattering/domain matrix and reconcile the backlog with the actual code. Delegate independent reviews to physics-contract-reviewer, performance-engineer, and scientific-ux-reviewer. Do not change source files, configuration, golden fixtures, dependencies, or GitHub state. Return evidence, priorities, and concrete assignments for the next stage.

## Future implementation assignment

> Implement only <task ID> on base <SHA>, within <allowed paths>, following <approved contract>. Preserve unrelated changes. Satisfy <acceptance criteria>. Send the diff to independent-validation-reviewer; do not merge or deploy automatically.

This is a template for a future assignment, not authorization to implement now. The execution environment must separately grant editing capabilities to an implementation agent.

## Working order

Physics contract → Numerics → independent Physics/Validation review. Runtime and performance baseline investigations can proceed in parallel. After schema agreement, proceed with Reproducibility and UX. Optimize core only after the mathematical contract is established. The author must not be the sole final reviewer of their own change. The scientific owner confirms the physics.

## Profiles

- review-coordinator.md
- physics-contract-reviewer.md
- numerics-inference-engineer.md
- performance-engineer.md
- compute-runtime-engineer.md
- scientific-ux-reviewer.md
- reproducibility-engineer.md
- independent-validation-reviewer.md
