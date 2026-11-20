# Codex project instructions

Read `CLAUDE.md` and `CONTRIBUTING.md` for the shared engineering rules. Codex
roles are in `.codex/agents/*.toml`; Claude profiles do not choose Codex models.

## Parent workflow skills

The parent uses the installed Matt Pocock Skills, Ponytail and Superpowers
plugins for the tasks below. Resolve skill locations from the session catalog
and read the selected `SKILL.md` before applying it. Keep machine-specific paths
out of project instructions. Subagents follow the role skill requirements below.

- **Matt Pocock Skills:** use `mattpocock-skills:implement` for existing specs
  or tickets, `diagnosing-bugs` for reported failures, `codebase-design` for
  module boundaries, `code-review` for requested branch/PR reviews, and
  `writing-for-agents` when editing agent instructions. Other skills follow
  their declared triggers.
- **Ponytail:** for coding tasks, load
  `engineering-suite-ponytail:entry-ponytail` and its selected workflow.
  Prefer existing code, the standard library and the smallest root-cause fix.
  Use the audit or complexity-review workflows when that review is requested.
- **Superpowers:** load `superpowers:using-superpowers` at task start, then
  select the applicable discovery, planning, debugging, TDD and verification
  workflows. Use worktree and delegation workflows within the policy below.

Combine compatible skill steps into one workflow, reusing the existing spec
and validation evidence. Ask about material decisions the task leaves open.
Project rules govern model routing, concurrency, review count, validation
ownership and publishing when plugin guidance differs. Skills do not supply
human physicist confirmation.

## Delegation and model routing

Use cost-conscious delegation proactively when it reduces duplicated reasoning.
This file explicitly authorizes the parent to spawn the relevant Codex agents.
Do small, clear, single-file tasks directly. Do not create an agent merely to run
a trivial command, relay a result or wait for CI.

For a substantial task, the parent owns scope, acceptance criteria, integration
and the final answer. Delegate a bounded implementation to `worker` when it can
own a coherent change. Use `explorer` only if the owning code is not yet known;
use `docs_worker` for an independent, sufficiently large documentation change.
Do not implement the same delegated change in parallel yourself.

Use one `reviewer` for integration correctness on nontrivial changes. Small
documentation or mechanical changes need focused validation. Add a
security-specific review for a concrete security-sensitive surface.

- Use `numerics_reviewer` for changes to solvers, numerical integration or
  interpolation, tolerances, fitting objectives or uncertainty estimates. It
  checks algorithm reliability and identifiability.
- Use `physics_reviewer` for changes to physical formulas, units, physical
  scales, model assumptions, applicability or fit interpretation. A solver or
  fit change under a fixed physical contract needs numerical review. If the
  change also affects that contract or its interpretation, assign both roles
  distinct questions and share validation evidence.

For a review follow-up, send the new diff, outstanding findings and fresh
validation evidence to the same reviewer when available.

Honor each role's configured model and effort. For a client exposing only
explicit spawn parameters, use the model/effort from the matching TOML. Use a
fresh context (`fork_turns="none"` where available) with a compact handoff:
checkout, task, owned files, constraints, acceptance criteria and known evidence.
Never forward the full chat by default. Agent output should fit in about 250
words plus necessary findings. At most two subagents run concurrently. Only one
writer owns a file; reviewers are read-only by instruction, not a separate sandbox.

Escalate reasoning only for a specific unresolved ambiguity or repeated failed
approach. State the reason before escalation. Do not use Astra, Max or Ultra by
default. A model's availability or a UI override can differ from the repository
configuration; report an unavailable role instead of silently substituting an
expensive model. Existing chats may need restarting to discover custom roles.

## Role skills

Each role's `developer_instructions` in `.codex/agents/*.toml` defines its required
skills and conditional triggers. Load only matching skills and referenced branches.
Resolve installed skills from the session catalog and read repository skills at
their explicit paths. `explorer`, `physics_reviewer` and `numerics_reviewer` use
repository and user skills with plugins disabled. The parent owns any plugin
workflow that applies to the overall task. Report a missing required skill before
dependent work. Skills guide the assigned task within its file ownership,
read-only and validation boundaries.

`scientific-computing` lives in `.agents/skills/scientific-computing/SKILL.md`.
The numerical reviewer loads it for its review; workers and physical reviewers
load it for symbolic or numerical work. Read only the relevant reference branch.

The parent includes required skill names and resolved paths in explicit handoffs
when native role loading is unavailable. Read `docs/codex-orchestration.md` when
setting up roles, checking skill discovery or measuring usage.

## Validation and completion

Assign one validation owner (parent or `validator`) per revision. Workers run
focused checks; reviewers consume that evidence rather than rerunning the full
suite. Run the required `pnpm check` once before pushing the final revision.
After a failure, rerun the affected checks; repeat a full suite only if the fix
or repository requirements justify it. Keep command logs outside tracked files,
return concise failure excerpts, and do not repeatedly print unchanged CI state.
Do not mark expected failures as a complete implementation or merge a failing
reproduction-only PR. Human physicist confirmation stays distinct from agent review.

## GitHub operations

Use Git for commits and push. Prefer GitHub MCP for PR operations. If MCP returns
403, use the GitHub API/CLI with the existing Git authorization, without exposing
or saving credentials. Do not open a browser for routine GitHub operations.
Never infer permission to merge from permission to implement; follow the user's
explicit publishing/merge instructions and repository protections.

See `docs/codex-orchestration.md` for setup, role selection and limitations.
