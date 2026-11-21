# Reviewing the SeeBand Web band-composition design v0.7

Read the [technical design document](../2026-11-21-band-composition-design.md) for the formulas and proposed changes to P18. The [evidence index](evidence.json) lists commands, conditions, units, tolerances and the SHA-256 digests of saved outputs. To try the [interactive Fit and Guide prototype](fit-guide.html), select **Download raw file** on GitHub and open the downloaded HTML in a browser.

## Replaying the checks from this branch

From the repository root, install the project dependencies with `uv sync` and `pnpm install --frozen-lockfile`, then run:

```sh
.venv/bin/python scripts/verify_band_composition_design.py
.venv/bin/python scripts/verify_spb_design_coefficients.py
.venv/bin/python scripts/verify_skb_design_reference.py
.venv/bin/python scripts/verify_mixed_scattering_design.py
PYTHONPATH=packages/seeband_core/src .venv/bin/python scripts/verify_mixed_scattering_design.py --legacy
```

The first four commands reproduce CHARGE, SPB, SKB and MIX. The fifth (MIX-LEGACY) compares ρ, S and Hall with this branch's `seeband_core.math_module` using the same chemical potentials and integrals as inputs. The [index](evidence.json) also gives the commands for the two prototypes. The Fit and Guide browser check requires Chrome.

**P18 archive.** This repository has no published ref for `8e4f98d`. Three rows retain results from that historical checkout:

- **P18-BASE** recorded 113 passing tests. The three test files are absent from this branch.
- **DPB-HALL** exceeded the proposed tolerance. On this branch the script stops at the import of `seeband_core.explicit_transport`.
- **MIX-P18** preserves the historical `--legacy` output. The branch replay of the same comparison (MIX-LEGACY) uses the version of the core in this PR. The last digits of the S and Hall errors differ. Both logs are linked below.

Use the SHA-256 digest to check a saved file's integrity. The manifest's `replay_status` identifies runs reproduced from this branch. Archive entries retain their historical command. E2E is planned.

## Using Fit and Guide

The [prototype](fit-guide.html) lets you build a model with one to three bands and inspect the fields for each fit mode. Guide shows the comparison across modes. With three bands, the Band gap row identifies the edges that determine the gap. TDD §15.1 gives examples where the lowest conduction band changes, edges coincide, or the bands overlap. Prototype input values are illustrative.

FitPage has two areas. On the left, Data sits alongside four ChartGrid slots. On the right, FitPanel is followed by Parameters, Model and Result. In Model, each of the one to three rows specifies VB or CB and Parabolic or Kane. This composition determines the model name. Fit mode, a shared scattering mechanism, valley degeneracies and the temperature range stay in Model. The researcher enters parameter values, holds and fit bounds in Parameters.

For example, set Band 1 to VB Parabolic, Band 2 to CB Parabolic and Band 3 to VB Parabolic. The label reads **3 SPB**. Remove Band 3 to obtain **DPB**, then change Band 2 to Kane for **1 SKB + 1 SPB**. Model now offers only acPh, and Parameters gains the Band 2 nonparabolicity field. The planned E2E check covers preserving bounds and recalculating curves through these transitions.

The [Parameters and Model field dictionary](../band-parameter-labels.json) lists labels, units, definitions, tooltips and the SPB matrix for every fit mode and scattering mechanism. TDD §15 covers all six model families.

## Results and open checks

| ID           | Scope                                                                 | Result                                                                                                                                | Evidence                                                            |
| ------------ | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| P18-BASE     | P18 archive · domains, transport and explicit DPB fitting             | 113 tests passed in the historical checkout.                                                                                          | [pytest log](evidence/p18-baseline.txt)                             |
| CHARGE       | Shared μ(T), densities and band permutations                          | Maximum normalized residual 1.303 × 10⁻¹³.                                                                                            | [Output](evidence/verify_band_composition_design.txt)               |
| SPB          | Integrals and analytical formulas                                     | 36 cases. Maximum Hall error 1.017 × 10⁻¹⁰.                                                                                           | [Output](evidence/verify_spb_design_coefficients.txt)               |
| DPB-HALL     | P18 archive · core vs. independent formulas                           | 27 combinations and 81 temperature points. The Hall error of 1.172 × 10⁻⁶ at CB+CB / dis / 800 K exceeds the proposed 10⁻⁶ tolerance. | [Inputs and values](evidence/explicit_curves_spb_result.txt)        |
| SKB          | Acoustic SKB against Tables 1 and 2 of Lin and Liu                    | Calculated m_D/mₑ values of 0.952275 and 0.0387615, compared with the published 0.9523 and 0.03877.                                   | [Output](evidence/verify_skb_design_reference.txt)                  |
| MIX          | acPh + dis for parabolic bands                                        | 72 cases, both pure-scattering limits and three independent crossover temperatures.                                                   | [Output](evidence/mixed_reference.txt)                              |
| MIX-LEGACY   | Comparison with this PR's math_module at shared μ and integral values | 100, 300 and 800 K. Maximum Hall error 4.495 × 10⁻⁷ for a tolerance of 3 × 10⁻⁵.                                                      | [Branch output](evidence/mixed_legacy_pr.txt)                       |
| MIX-P18      | P18 archive · historical run with --legacy                            | The comparison passed in the historical checkout.                                                                                     | [Archived output](evidence/verify_mixed_scattering_design.txt)      |
| UI-FIT-GUIDE | Packaged v0.7 prototype                                               | 270 field configurations, holds, bounds, Guide and the three-band gap. Chrome at widths of 960 and 320 px.                            | [Output](evidence/fit-guide-v0.7.txt)                               |
| UI-MODEL     | Earlier Model prototype                                               | Checked labels, row counts and Kane restrictions.                                                                                     | [Output](evidence/mock_result.txt)                                  |
| E2E          | New band builder → Parameters → calculate → fit → session             | Pending implementation. The full end-to-end matrix of 270 allowed configurations has yet to run.                                      | [Criteria in §1.4 and §8](../2026-11-21-band-composition-design.md) |

## Giving feedback

Include the check ID or section, the claim under review, the inputs, and the expected and observed behavior. Link to the file or primary source. For a proposed feature, specify an acceptance criterion. Agreement between independent calculations supports a formula at the points tested. Interpreting a particular sample still depends on the researcher's physical assumptions.
