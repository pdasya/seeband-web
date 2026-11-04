---
name: documentation
description: Documentation rules for SeeBand Web. Use when a change affects behaviour, public API, setup, deployment, formulas or results, and when writing or editing a README, the changelog, Conventions, the user guide or a decision record.
---

# SeeBand Web documentation

Documentation changes in the same pull request as the code it describes.

## What to update

| Change                            | Update                                                         |
| --------------------------------- | -------------------------------------------------------------- |
| Setup or check commands           | root `README.md`                                               |
| Purpose or use of a package       | that package's `README.md`                                     |
| Formula, unit or model assumption | Conventions page in `apps/site`, matching the core exactly     |
| Results that differ from before   | changelog: what changed, why, and from which version           |
| Known error added or fixed        | known-issue registry and the note on the Conventions page      |
| Decision that is hard to reverse  | decision record: the choice, its reason, and what was rejected |

## How to write

- Write English in the repository. Public pages also need German where the site provides it.
- Lead with the answer. Prefer short sentences and concrete values with units.
- State known issues plainly. Do not soften them or leave them out.
- Do not document what the code or a linter already makes obvious.
- Use numbers only from real runs, and name the environment when a measurement depends on it.
- Label synthetic data as synthetic.
- Keep the original SeeBand attribution with any copied code or adapted text.
