# Third-party skills

| Skill                         | Source                                                                                                                                            | Commit                                     | License                                                                  | Copied or linked                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------ | -------------------------------------------------- |
| `vercel-composition-patterns` | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/composition-patterns) | `1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62` | MIT, declared in `SKILL.md`; the upstream repository has no license file | copied, unmodified                                 |
| `fastapi`                     | bundled in the installed `fastapi` package                                                                                                        | follows `uv.lock`                          | MIT, the package license                                                 | linked by `scripts/setup-claude.sh`, not committed |

To update a copied skill, read the upstream diff first, copy the new files, and update the commit here.
