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
PYTHONPATH=packages/seeband_core/src .venv/bin/python scripts/verify_skb_design_reference.py --core
.venv/bin/python scripts/verify_parabolic_mass_identifiability.py
```

The first four commands reproduce CHARGE, SPB, SKB and MIX. The fifth (MIX-LEGACY) compares ρ, S and Hall with this branch's `seeband_core.math_module` using the same chemical potentials and integrals as inputs. The sixth (SKB-CORE) imports the four SeeBand physical constants, reproduces all 11 SKBcal masses and tests the isolated acoustic band against its dimensional integrals and its SPB limit. The seventh (MASS-SCALE) checks absolute mass scaling and separates the explicit conductivity weight from the effect of mass on the charge balance. The [index](evidence.json) also gives the commands for the two prototypes. The Fit and Guide browser check requires Chrome.

**P18 archive.** The [original P18 revision](https://github.com/pdasya/seeband-web/commit/8e4f98d78c3868c65f5e22b4e359061aca3f7ece) is now reachable from the [separate P18 branch](https://github.com/pdasya/seeband-web/tree/codex/p18-hall-quadrature). Three rows retain the original outputs:

- **P18-BASE** recorded 113 passing tests. The three test files are absent from this branch.
- **DPB-HALL** exceeded the proposed tolerance. The strict audit reproduces the failure on the original P18 revision. DPB-HALL-FIX records the result with corrected quadrature.
- **MIX-P18** preserves the historical `--legacy` output. The branch replay of the same comparison (MIX-LEGACY) uses the version of the core in this PR. The last digits of the S and Hall errors differ. Both logs are linked below.

Use the SHA-256 digest to check a saved file's integrity. The manifest's `replay_status` identifies runs reproduced from this branch. Archive entries retain their historical command. E2E is planned.

## Replaying the P18 Hall comparison

From the root of this review branch, fetch P18 and run the same audit against both revisions. The expected outcome for the first run is a nonzero exit at the 10⁻⁶ Hall budget. The second must pass both that budget and the 10⁻⁷ regression target.

```sh
audit="$PWD/docs/superpowers/specs/band-composition-v0.7/evidence/verify_explicit_curves_spb.py"
git fetch origin refs/heads/codex/p18-hall-quadrature
git worktree add --detach ../p18-hall-before 8e4f98d78c3868c65f5e22b4e359061aca3f7ece
git worktree add --detach ../p18-hall-after a7943506412eb82856ad2459984632190315bb64
(cd ../p18-hall-before && PYTHONPATH=packages/seeband_core/src uv run --frozen python "$audit")
(cd ../p18-hall-after && PYTHONPATH=packages/seeband_core/src uv run --frozen python "$audit")
(cd ../p18-hall-after && uv run --frozen pytest -q packages/seeband_core/tests/test_transport_hall_quadrature.py)
```

For λ = 0 (acPh and dis), the Hall integrand contains √x at the band edge. The substitution x = t² gives √x dx = 2t² dt. The kernel retains the linear energy grid when the integration window lies entirely above the edge. The moment test compares with ½ F₋½(η) in the unnormalized Fermi-integral convention at a relative tolerance of 10⁻¹⁰, including depleted and degenerate bands. At η = −40, −6, −2, 0, 3, 10 and 60, the maximum relative moment error fell from 1.174 × 10⁻⁶ to 3.908 × 10⁻¹⁴ against a 60-digit polylogarithm reference.

The end-to-end audit covers 27 configuration/scattering/mode combinations at 100, 300 and 800 K. Of its 81 evaluated points, 27 use the fit mode that returns Hall. The Hall error is scaled by the sum of absolute channel Hall contributions, including near compensation.

## Using Fit and Guide

The [prototype](fit-guide.html) lets you build a model with one to three bands and inspect the fields for each fit mode. Guide shows the comparison across modes. With three bands, the Band gap row identifies the edges that determine the gap. TDD §15.1 gives examples where the lowest conduction band changes, edges coincide, or the bands overlap. Prototype input values are illustrative.

FitPage has two areas. On the left, Data sits alongside four ChartGrid slots. On the right, FitPanel is followed by Parameters, Model and Result. In Model, each of the one to three rows specifies VB or CB and Parabolic or Kane. This composition determines the model name. Fit mode, a shared scattering mechanism, valley degeneracies and the temperature range stay in Model. The researcher enters parameter values, holds and fit bounds in Parameters.

For example, set Band 1 to VB Parabolic, Band 2 to CB Parabolic and Band 3 to VB Parabolic. The label reads **3 SPB**. Remove Band 3 to obtain **DPB**, then change Band 2 to Kane for **1 SKB + 1 SPB**. Model now offers only acPh, and Parameters gains the Band 2 nonparabolicity field. The planned E2E check covers preserving bounds and recalculating curves through these transitions.

The [Parameters and Model field dictionary](../band-parameter-labels.json) lists labels, units, definitions, tooltips and the SPB matrix for every fit mode and scattering mechanism. TDD §15 covers all six model families.

## Results and open checks

| ID           | Scope                                                                                                  | Result                                                                                                                                                                   | Evidence                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| P18-BASE     | P18 archive · domains, transport and explicit DPB fitting                                              | 113 tests passed in the historical checkout.                                                                                                                             | [pytest log](evidence/p18-baseline.txt)                             |
| CHARGE       | Shared μ(T), densities and band permutations                                                           | Maximum normalized residual 1.303 × 10⁻¹³.                                                                                                                               | [Output](evidence/verify_band_composition_design.txt)               |
| SPB          | Integrals and analytical formulas                                                                      | 36 cases. Maximum Hall error 1.017 × 10⁻¹⁰.                                                                                                                              | [Output](evidence/verify_spb_design_coefficients.txt)               |
| DPB-HALL     | P18 archive · core vs. independent formulas                                                            | 27 combinations and 81 temperature points. The Hall error of 1.172 × 10⁻⁶ at CB+CB / dis / 800 K exceeds the proposed 10⁻⁶ tolerance.                                    | [Inputs and values](evidence/explicit_curves_spb_result.txt)        |
| DPB-HALL-FIX | Published P18 · corrected endpoint quadrature                                                          | Maximum scaled Hall error 5.0771 × 10⁻¹¹, down from 1.1716 × 10⁻⁶ for CB+CB / dis / 800 K.                                                                               | [Corrected run](evidence/dpb_hall_p18_fixed.txt)                    |
| SKB          | Acoustic SKB against Tables 1 and 2 of Lin and Liu                                                     | Calculated m_D/mₑ values of 0.952275 and 0.0387615, compared with the published 0.9523 and 0.03877.                                                                      | [Output](evidence/verify_skb_design_reference.txt)                  |
| SKB-CORE     | All 11 Lin–Liu SKBcal masses with core constants, absolute transport, parabolic limit and valley count | Maximum table error 0.02188%. The 108 synthetic cases cover both charge signs and N = 1, 2, 6. The maximum discrepancy at the exact SPB limit is 1.867 × 10⁻¹¹.          | [Per-row results and limits](evidence/verify_skb_core.txt)          |
| MASS-SCALE   | Two- and three-band parabolic mass identifiability                                                     | 54 common-scale checks. Nearly coincident edges admit 39/39 longitudinal points along a prescribed path. Separated edges admit 3/39 after re-solving the charge balance. | [Inputs, gates and results](evidence/mass_identifiability.txt)      |
| MIX          | acPh + dis for parabolic bands                                                                         | 72 cases, both pure-scattering limits and three independent crossover temperatures.                                                                                      | [Output](evidence/mixed_reference.txt)                              |
| MIX-LEGACY   | Comparison with this PR's math_module at shared μ and integral values                                  | 100, 300 and 800 K. Maximum Hall error 4.495 × 10⁻⁷ for a tolerance of 3 × 10⁻⁵.                                                                                         | [Branch output](evidence/mixed_legacy_pr.txt)                       |
| MIX-P18      | P18 archive · historical run with --legacy                                                             | The comparison passed in the historical checkout.                                                                                                                        | [Archived output](evidence/verify_mixed_scattering_design.txt)      |
| UI-FIT-GUIDE | Packaged v0.7 prototype                                                                                | 270 field configurations, holds, bounds, Guide and the three-band gap. Chrome at widths of 960 and 320 px.                                                               | [Output](evidence/fit-guide-v0.7.txt)                               |
| UI-MODEL     | Earlier Model prototype                                                                                | Checked labels, row counts and Kane restrictions.                                                                                                                        | [Output](evidence/mock_result.txt)                                  |
| E2E          | New band builder → Parameters → calculate → fit → session                                              | Pending implementation. The full end-to-end matrix of 270 allowed configurations has yet to run.                                                                         | [Criteria in §1.4 and §8](../2026-11-21-band-composition-design.md) |

## Giving feedback

Include the check ID or section, the claim under review, the inputs, and the expected and observed behavior. Link to the file or primary source. For a proposed feature, specify an acceptance criterion. Agreement between independent calculations supports a formula at the points tested. Interpreting a particular sample still depends on the researcher's physical assumptions.
