# Third-party skills

| Skill                         | Source                                                                                                                                            | Commit                                     | License                                                                  | Copied or linked                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------ | -------------------------------------------------- |
| `vercel-composition-patterns` | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/composition-patterns) | `1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62` | MIT, declared in `SKILL.md`; the upstream repository has no license file | copied, unmodified                                 |
| `fastapi`                     | bundled in the installed `fastapi` package                                                                                                        | follows `uv.lock`                          | MIT, the package license                                                 | linked by `scripts/setup-claude.sh`, not committed |

To update a copied skill, read the upstream diff first, copy the new files, and update the commit here.

# Third-party agents

| Agents                                                                                                               | Source                                                                                               | Commit                                     | License                                  |
| -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------ | ---------------------------------------- |
| `python-reviewer`, `fastapi-reviewer`, `typescript-reviewer`, `react-reviewer`, `security-reviewer`, `code-reviewer` | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/b38be6a7f6350964d59328b52f0624e1d1d552d1/agents) | `b38be6a7f6350964d59328b52f0624e1d1d552d1` | MIT, in `.claude/agents/ECC-LICENSE.txt` |

These copies differ from upstream on purpose:

- Each has a "SeeBand Web rules" section, which wins over the rest of the file.
- They run when asked, so "MUST BE USED" and "PROACTIVELY" are gone from their descriptions.
- Commands use `pnpm` and `uv`, and references to ECC skills and commands that this project does not have are removed.

To update them, read the upstream diff first, then copy the new files and reapply these changes.
