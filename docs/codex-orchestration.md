# Codex orchestration

Codex project settings live in `.codex/config.toml`, role definitions in
`.codex/agents/*.toml`, and the routing policy in `AGENTS.md`. `CLAUDE.md` remains
the shared engineering policy. Claude's `model: sonnet` / `model: opus` metadata
is not a Codex model selection mechanism.

## Defaults and roles

| Owner             | Model       | Effort | Assignment                                                      |
| ----------------- | ----------- | ------ | --------------------------------------------------------------- |
| Parent            | GPT-6.2 Sol | low    | Scope, acceptance, integration, user communication              |
| explorer          | GPT-6.2 Sol | medium | Narrow read-only code mapping when ownership is unknown         |
| worker            | GPT-6.2 Sol | medium | Bounded implementation, focused tests                           |
| docs_worker       | GPT-6.2 Sol | medium | Assigned documentation based on verified facts                  |
| validator         | GPT-6.2 Sol | medium | Run the agreed checks once, report concise results              |
| reviewer          | GPT-6.2 Sol | medium | Independent correctness review of the final diff                |
| numerics_reviewer | GPT-6.2 Sol | medium | Solver reliability, numerical stability and fit identifiability |
| physics_reviewer  | GPT-6.2 Sol | high   | Independent formulas, units, limits and fit interpretation      |

An unclassified spawn defaults to GPT-6.2 Sol/medium. Explicit UI or session
choices can override the parent model. Inspect the composer in an existing chat
and start a fresh chat to verify current role settings.

Agents share the parent's permission boundary. Apps remain disabled in every
role. Roles using plugin skills enable plugins; explorer, physics_reviewer and numerics_reviewer
use repository/user skills with plugins disabled. Reviewers being read-only is an
instruction, not a separate operating-system sandbox. The parent handles GitHub
and all external publishing.

## Skills by role

The `developer_instructions` in each role's TOML file define its required skills
and triggers. The parent owns the project-wide plugin workflows in `AGENTS.md`.
Within a role, load the skills whose triggers match the assignment.

| Role              | Required for every assignment                              | Required when triggered                                                                                                                                                                                                                                                                                                                          |
| ----------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| explorer          |                                                            | Project `architecture` when tracing core/API/web boundaries.                                                                                                                                                                                                                                                                                     |
| worker            | Project `architecture` before edits                        | `documentation` for public behavior, results or docs. Ponytail entry and coding workflows for coding. `diagnosing-bugs` for bugs. `tdd` for changed feature or bug behavior. Composition guidance for React APIs or state. `condensed-matter-theory` for assigned physics implementation. `scientific-computing` for symbolic or numerical work. |
| docs_worker       | Project `documentation`                                    | `writing-for-agents` for agent instructions. `architecture` for boundaries or numerical policy. `condensed-matter-theory` when evaluating physical explanations.                                                                                                                                                                                 |
| validator         | `verification-before-completion` before validation         | `systematic-debugging` when assigned failure diagnosis.                                                                                                                                                                                                                                                                                          |
| reviewer          | Project `architecture`                                     | `documentation` for public claims or docs. Ponytail entry and `ponytail-review` when assigned complexity review.                                                                                                                                                                                                                                 |
| physics_reviewer  | `condensed-matter-theory`, `architecture`, physics profile | `scientific-computing` for symbolic or numerical verification. Theory references for the specific physical question.                                                                                                                                                                                                                             |
| numerics_reviewer | `scientific-computing`, `architecture`, numerics profile   | `documentation` for numerical claims in docs.                                                                                                                                                                                                                                                                                                    |

`scientific-computing` is a repository skill at
`.agents/skills/scientific-computing/SKILL.md`, discoverable through Codex's
repository skill directory and readable directly from role instructions. It is
required for numerical reviews, and conditional for workers handling symbolic
algebra, solvers, integration/interpolation, tolerances, Jacobians, fit objectives
or uncertainty estimates. Physics reviewers load it for symbolic/numerical
verification. Its references separate symbolic work, numerical algorithms and
inverse problems; they do not add runtime dependencies. SymPy remains optional
scratch tooling. NumPy/SciPy/mpmath are used only when the task needs them and the
environment provides them; the skill does not authorize installations.

The Codex numerics role adapts `.claude/agents/numerics-inference-engineer.md`.
It reviews the approved model's computation, while physics_reviewer reviews its
physical validity. It does not change solvers, fixtures or tolerances itself.
Use Sol/medium by default and escalate only for a named unresolved ambiguity.

Repository skills are read directly from `.claude/skills/*/SKILL.md` or
`.agents/skills/*/SKILL.md`; they do not
need a plugin. The physics profile is `.claude/agents/physics-reviewer.md`, whose
Claude model metadata does not select the Codex model.

User skills and plugin skills are local prerequisites, not dependencies installed
by cloning this repository. Install `condensed-matter-theory` in the user's Codex
skills directory (on the setup machine, `~/.codex/skills/condensed-matter-theory/`,
including its `references/`). Enable the Matt Pocock Skills, Ponytail and
Superpowers plugins for roles using their skills. Resolve their exact skill names
and `SKILL.md` paths from the current session catalog; keep machine-specific home
paths and versioned plugin-cache paths out of role files.

Skills inherit from the parent. Plugin availability depends on installation and
client discovery. `explorer`, `physics_reviewer` and `numerics_reviewer` use
repository and user skills with plugins disabled. The parent applies any plugin
workflow needed for the overall task. With explicit model/effort handoffs, send
the role instructions and the resolved skill paths the child needs. If a required
skill is absent, report it before dependent work. Load the relevant reference
branches and follow the assigned write scope and validation ownership.

After changing these assignments, start a new chat and check role/skill discovery.
Static TOML and path checks establish configuration integrity; use a runtime check
to establish that a particular client exposes installed plugin skills to a freshly
spawned role. See the official
[subagent skill inheritance documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## Routing examples

Apply the review triggers in [AGENTS.md](../AGENTS.md#delegation-and-model-routing).

- One-line copy correction: parent edits and checks formatting; no team.
- Ordinary bug: worker owns the fix and focused checks, reviewer inspects the
  final diff, parent or validator performs final validation once.
- Solver tolerance under a fixed physical contract: numerics_reviewer checks
  convergence and reliability. Reviewer checks integration for a nontrivial diff.
- Fit change affecting both the algorithm and a physical assumption:
  numerics_reviewer checks convergence and identifiability, physics_reviewer
  checks the assumption and its limits, and reviewer checks integration. Share
  the same validation evidence and keep the two-child concurrency limit.
- Unknown failure: explorer first maps the path and evidence. Only then assign
  implementation. Do not make two agents independently explore the entire repo.

At most two subagents run concurrently. Parallelize independent reads or disjoint
files, not two writers on the same file. Send a fresh, small handoff: checkout,
base/head, objective, owned files, constraints, acceptance criteria and evidence.
Do not copy the whole chat into every agent. Reuse the same agent for a revision
when its existing context is useful; start fresh when its old task is unrelated.
For review follow-ups, send the new diff and unresolved findings with any fresh
validation evidence.

When a client exposes `spawn_agent` with explicit model settings rather than a
role selector, the parent must read the matching TOML and pass its model/effort.
`fork_turns="none"` plus the compact handoff avoids inherited conversation bloat.

## Validation and publishing

Workers run focused tests. Reviewers consume those results and run only a missing
reproduction when needed. One parent or validator owns the final `pnpm check`.
A tiny configuration/documentation-only change needs TOML parsing, Codex config
loading, formatting and a policy review, not thousands of numerical/browser tests.
The full suite still runs when required before publishing code changes.

Keep logs in temporary files and return counts, exit codes and short failure
excerpts. Do not keep printing unchanged CI snapshots. Use compact waits, and
rerun only after a change or a justified failure. Never merge expected red tests
as if they were a completed fix. A physicist's confirmation is a separate release
requirement and cannot be supplied by an AI review.

Use native Git for commits/push. Use GitHub MCP first, then the GitHub API/CLI
with existing authorized credentials when MCP returns 403. Do not open the
browser for routine repository operations, print tokens, or create another
credential just to work around the connector.

## Activating the configuration

1. Open the repository checkout or worktree itself as the Codex project, rather
   than only its parent `SeeBand` folder. Start a new chat there. Clients supporting native custom agents can then load
   these roles; otherwise use explicit model/effort handoffs as described above. The configuration travels with Git after it is merged.
2. The actual Git root `seeband-web` must be trusted. Worktrees can resolve trust
   against that shared root. Trust is a user-local setting and is not installed by cloning these files.
   Configure it through Codex for this repository. Do not relax the sandbox or
   approval policy to make the roles load.
3. Choose Sol/Light in the composer if the UI retains a different explicit model.
   Ask: "Use the project routing policy; delegate the bounded implementation to
   worker, then use one relevant reviewer."
4. Check that Codex discovers the role names and their descriptions. An old chat
   may have loaded its available roles before the files existed.

Project settings can be ignored when a repository is untrusted. CLI config
validation alone is therefore insufficient: check the effective config and role
discovery as well. Configured model IDs must be available to the account; do not
silently fall back to a more expensive model if one is unavailable.

## Limits and measuring the result

Subagents share the account's usage allowance. Parallel agents can reduce elapsed
time while increasing total tokens. Check the account dashboard for its usage
windows and reset times.
A long-lived root chat also carries context costs. Prefer a fresh task chat with
a short handoff when moving to an unrelated issue; keep project knowledge in files.

Compare similar tasks using the role, model, effort, elapsed time, token breakdown,
review rounds and repeated checks. Measure through acceptance so follow-up work
counts. Increase effort after identifying the unresolved problem it should address.

### Worker pilot, 2026-11-18

Both models received the same worker instructions at medium effort in isolated
copies of `def1eef`. Each task ran as a concurrent pair with explicit model
selection and the inherited speed preference. Elapsed time covers each child
turn, including tools and tests.

| Task                      | Model       | Elapsed | Uncached input | Cached input | Output | Focused tests |
| ------------------------- | ----------- | ------: | -------------: | -----------: | -----: | ------------: |
| Fortran exponent import   | GPT-6.1 Sol |  88.8 s |         58,012 |      362,752 |  3,065 |           214 |
| Fortran exponent import   | GPT-6.2 Sol |  80.5 s |         67,034 |      434,688 |  2,611 |           203 |
| Multiline export comments | GPT-6.1 Sol |  65.2 s |         54,059 |      305,408 |  2,294 |            34 |
| Multiline export comments | GPT-6.2 Sol |  61.9 s |         48,850 |      326,912 |  2,012 |            34 |

Both models passed the same independent acceptance cases (six for import and
seven for export). Focused test counts include each worker's own regression
cases. GPT-6.2 Sol finished faster in both pairs, with less output and more input
in aggregate. This small pilot measures implementation on two tasks. Token
counts are useful for workload comparisons. The account dashboard reports the
shared subscription allowance. The experimental patches stayed in the pilot copies.

## GPT-6.2 Sol role verification, 2026-11-18

All seven custom roles completed a read-only loading check in Codex Desktop.
Each launch selected the role by name with `fork_turns="none"` and used its
configured model and effort. At most two children ran concurrently. The parent
checked the model and effort in the launch logs and verified the skill reads in
the tool output.

| Role                | Observed model | Observed effort | Assigned skill files read |
| ------------------- | -------------- | --------------- | ------------------------- |
| `worker`            | `gpt-6.2-sol`  | medium          | 9/9                       |
| `docs_worker`       | `gpt-6.2-sol`  | medium          | 4/4                       |
| `reviewer`          | `gpt-6.2-sol`  | medium          | 4/4                       |
| `validator`         | `gpt-6.2-sol`  | medium          | 2/2                       |
| `explorer`          | `gpt-6.2-sol`  | medium          | 1/1                       |
| `numerics_reviewer` | `gpt-6.2-sol`  | medium          | 3/3                       |
| `physics_reviewer`  | `gpt-6.2-sol`  | high            | 3/3                       |

All 26 assigned skill reads succeeded, including skills with conditional
triggers. Each child resolved installed skills from its own catalog and read
repository skills at the paths in its role instructions. Both scientific
reviewers also read their review profiles and relevant reference sections. The
check covered Desktop launch, discovery and file loading. Workflow execution
and CLI skill discovery were outside its scope.

## Setup verification, 2026-11-14

The local setup added the actual `seeband-web` root to trusted projects and saved
`~/.codex/config.toml.before-seeband-trust.bak`. Global model defaults, sandbox and
approval policy were unchanged. Other machines need their own trust decision.

- All seven TOML files parse with Python `tomllib`.
- Installed Codex CLI `0.167.0-alpha.3.2` accepts the project in strict-config mode.
- Native `codex debug prompt-input` discovers the custom role descriptions after
  the repository trust entry is applied; no model response is generated by this check.
- The local model catalog advertises both `gpt-6-luna` and `gpt-6.1-sol`.
- A small read-only audit was delegated to Luna/medium with a fresh context and
  completed successfully. This verifies that model override in the current chat's
  delegation tools works; it does not prove this old chat automatically reloads
  native custom-role files.

Sources: [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

### Fresh-role skill loading (2026-11-14)

This is the original six-role snapshot, before adding `scientific-computing` and
`numerics_reviewer`; the follow-up check below covers those additions.

Six new child sessions were launched through the desktop app's `spawn_agent`,
using each custom role with `fork_turns="none"` and at most two children running
concurrently. Each child read its role TOML and probed every assigned skill,
including conditional skills. Installed skill paths were resolved from the
child's own session catalog; the parent supplied no installed skill paths or
skill bodies. Repository skills were read through the paths in the role TOMLs.

| Role             | Assigned skill files read | Installed skills found in child's catalog               | Additional reads                                                     |
| ---------------- | ------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------- |
| worker           | 7/7                       | Ponytail, diagnosing-bugs, tdd, condensed-matter-theory | Boltzmann and symbolic/numerical references                          |
| docs_worker      | 4/4                       | writing-for-agents, condensed-matter-theory             | Boltzmann reference                                                  |
| validator        | 2/2                       | verification-before-completion, systematic-debugging    | None                                                                 |
| reviewer         | 3/3                       | ponytail-review                                         | None                                                                 |
| physics_reviewer | 2/2                       | condensed-matter-theory                                 | Boltzmann and symbolic/numerical references; project physics profile |
| explorer         | 1/1                       | None assigned; repository-direct architecture skill     | None                                                                 |

Every child reported its resolved paths and a concrete instruction from each
skill as reading evidence. All 19 assigned skill reads succeeded, with no missing
catalog entries, fallback path searches or installation changes. The existing
plugin settings were sufficient in these fresh desktop child sessions.

This checks discovery and file loading, not task execution, scientific correctness
or enforcement of capability flags. The earlier standalone CLI prompt-input check
did not list the plugin skills; the desktop child results do not establish CLI
availability. Repeat this probe in the intended client after changing skill
installations or plugin settings. Probe prompts authorize reading conditional
skills for the check without executing their implementation/review workflows.

### Scientific-computing follow-up (2026-11-14)

The baseline had no `scientific-computing` skill in the repository or the child
catalog. The new repository skill lives in `.agents/skills/scientific-computing/`,
the native repository discovery location documented in
[Build skills](https://learn.chatgpt.com/docs/build-skills). It needs no plugin or
machine-specific installation. The role files retain a direct path for clients
whose skill catalogs have not refreshed.

Fresh desktop `worker` and `physics_reviewer` children, both with
`fork_turns="none"`, found the new skill in their own catalogs and read its
entrypoint plus all three references. No installed paths or skill bodies were
passed in their handoffs.

The current desktop parent had cached its role schema before the new role
existed: spawning `numerics_reviewer` returned `unknown agent_type`. A new
`codex debug prompt-input` discovered both the new role and skill. A separate
ephemeral, read-only `codex exec --strict-config` coordinator then launched one
native `numerics_reviewer` child and returned its completed report (exit 0).
That child found the skill in its own catalog and read all four skill files,
the project architecture skill and the existing numerics-inference profile.
Thus all three assigned roles loaded the new skill and its three branches.
Start a new desktop chat to refresh a cached native role list; editing the role
or weakening permissions is not needed. The existing explicit-handoff policy
remains available to clients without native role selection.

Both the physical and numerical reviewers correctly reasoned through three
synthetic cases: a scaled residual of `1e-12` despite a root error of `1`,
nonidentifiability of separate parameters in `y = a*b*x`, and the original
exclusion `x != 1` after cancelling `(x*x - 1)/(x - 1)`. These were analytic
application checks, not executed SciPy/SymPy calculations or production-model
validation. The physical and general reviewers reported no actionable findings.

All eight TOML files parse, the skill creator's `quick_validate.py` accepts the
new skill, relative reference links resolve, and formatting/whitespace checks
pass. No application code, golden results, dependency manifests or user-global
settings changed. Before publishing, the full `pnpm check` passed on the DX branch
based on current `origin/main`: 388 browser tests passed and 21 were skipped;
all 3414 Python tests passed with 33 warnings. Lint, formatting and type checks
also passed. The test run required only local environment setup, with no tracked
dependency changes.
