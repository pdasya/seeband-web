# Codex orchestration

Codex project settings live in `.codex/config.toml`, role definitions in
`.codex/agents/*.toml`, and the routing policy in `AGENTS.md`. `CLAUDE.md` remains
the shared engineering policy. Claude's `model: sonnet` / `model: opus` metadata
is not a Codex model selection mechanism.

## Defaults and roles

| Owner            | Model       | Effort | Assignment                                                 |
| ---------------- | ----------- | ------ | ---------------------------------------------------------- |
| Parent           | GPT-6.1 Sol | low    | Scope, acceptance, integration, user communication         |
| explorer         | GPT-6 Luna  | medium | Narrow read-only code mapping when ownership is unknown    |
| worker           | GPT-6.1 Sol | medium | Bounded implementation, focused tests                      |
| docs_worker      | GPT-6 Luna  | medium | Assigned documentation based on verified facts             |
| validator        | GPT-6 Luna  | medium | Run the agreed checks once, report concise results         |
| reviewer         | GPT-6.1 Sol | medium | Independent correctness review of the final diff           |
| physics_reviewer | GPT-6.1 Sol | high   | Independent formulas, units, limits and fit interpretation |

The default subagent is Luna/medium, so an unclassified spawn does not inherit an
expensive parent model. No Astra, Max or Ultra role is enabled by default. Explicit
UI/session choices can override the parent model; inspect the composer when an
existing chat still uses another selection. This configuration does not switch
the model of a turn already running.

Agents share the parent's permission boundary. Disabling apps/plugins in each
role limits unnecessary connector work; reviewers being read-only is also an
instruction, not a separate operating-system sandbox. The parent handles GitHub
and all external publishing.

## Routing examples

- One-line copy correction: parent edits and checks formatting; no team.
- Ordinary bug: worker owns the fix and focused checks, reviewer inspects the
  final diff, parent or validator performs final validation once.
- Numerical model fix: worker owns implementation, physics_reviewer checks the
  derivation and limits, reviewer checks integration without repeating physics.
- Unknown failure: explorer first maps the path and evidence. Only then assign
  implementation. Do not make two agents independently explore the entire repo.

At most two subagents run concurrently. Parallelize independent reads or disjoint
files, not two writers on the same file. Send a fresh, small handoff: checkout,
base/head, objective, owned files, constraints, acceptance criteria and evidence.
Do not copy the whole chat into every agent. Reuse the same agent for a revision
when its existing context is useful; start fresh when its old task is unrelated.

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

Subagents consume usage too. Parallel agents can reduce elapsed time while
increasing total tokens. This setup reduces duplicated context and work; it does
not increase the account's five-hour allowance or guarantee tasks per window.
A long-lived root chat also carries context costs. Prefer a fresh task chat with
a short handoff when moving to an unrelated issue; keep project knowledge in files.

For the next three representative tasks, record the selected role/model, duplicate
suite runs, elapsed time and usage shown by the client. Compare with prior tasks
of similar scope. If an agent costs more coordination than the work it replaces,
do that work directly. Increase effort only after naming an unresolved problem.
No API runner or separately billed Agents API service is introduced here.

## Verification performed on the setup machine

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
