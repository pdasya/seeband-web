# Reviewing the SeeBand Web band-composition design v0.7

Read the [technical design document](../2026-11-21-band-composition-design.md) for the formulas and proposed changes to P18. The [evidence index](evidence.json) lists commands, conditions, units, tolerances and the SHA-256 digests of saved outputs. To try the [interactive Fit and Guide prototype](fit-guide.html), select **Download raw file** on GitHub and open the downloaded HTML in a browser.

## Automated numerical checks

The core pytest suite runs the six Python design scripts in `scripts/`, including the SKB run with core constants and the mixed-scattering comparison with the legacy core. It also runs the valley-input and Kane-weight examples in this evidence directory. A failure propagates to `pnpm check` locally and to **Python tests (core)** on a pull request. To run just these cases from the repository root:

```sh
uv run --frozen pytest -q packages/seeband_core/tests/test_band_design_evidence.py
```

The ten cases exercise the numerical assertions and tolerances inside the reference calculations. Arithmetic comparisons use their per-observable tolerances. The SHA-256 values in the [manifest](evidence.json) identify the archived transcripts. Strict mypy covers the production core and API as configured in `pyproject.toml`. The reference scripts have runtime regression coverage. Calculations tied to a separate P18 checkout still use the revision-specific replay instructions below.

### Sensitivity checks for item 15

Each of the following changes was made separately in a disposable copy of the source. Run the pytest command above with `-k` to select a case, or copy the exact node ID from the [evidence index](evidence.json) and quote it on the command line. The unmodified scripts pass all ten cases.

| Pytest case                | Temporary change                                                                                         | Observed failure                                                                                                                                      |
| -------------------------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `spb`                      | In `momentum()`, negate the radial Seebeck coefficient `k1 / (q * temperature_k * k0)`.                  | The computed Seebeck sign disagreed with the specified carrier sign.                                                                                  |
| `skb-core`                 | In `kane()`, double the K4 drift mobility.                                                               | The conductivity at the parabolic limit differed from the independent SPB reference by about 100%. The relative tolerance was $10^{-8}$.              |
| `mixed`                    | In the direct integral in `channel()`, double the disorder rate in the sum of rates.                     | At the crossover temperature the mixed conductivity failed the half-acoustic-conductivity check. The absolute tolerance on this ratio was $10^{-12}$. |
| `skb-core`, `mixed-legacy` | Skip the call to `core_checks()` or `legacy()` while still returning success from the respective script. | In both cases pytest detected that the selected verification had never reported its result.                                                           |

These experiments exercised the reference scripts only. The scientific source, constants and tolerances are identical to the preceding revision.

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
.venv/bin/python scripts/verify_three_band_s_profile.py
```

The first four commands reproduce CHARGE, SPB, SKB and MIX. The fifth (MIX-LEGACY) compares ρ, S and Hall with this branch's `seeband_core.math_module` using the same chemical potentials and integrals as inputs. The sixth (SKB-CORE) imports the four SeeBand physical constants, reproduces all 11 SKBcal masses and tests the isolated acoustic band against its dimensional integrals and its SPB limit. The seventh (MASS-SCALE) checks absolute mass scaling and separates the explicit conductivity weight from the effect of mass on the charge balance. The eighth (S-PROFILE) reproduces the three-band flat-profile example displayed in Parameters. The [index](evidence.json) also gives the commands for the two prototypes. The Fit and Guide browser check requires Chrome. From the repository root, run:

```sh
FIT_GUIDE_CHROME=1 node docs/superpowers/specs/band-composition-v0.7/evidence/verify_fit_guide.mjs
PYTHONPATH=scripts .venv/bin/python docs/superpowers/specs/band-composition-v0.7/evidence/verify_valley_counts.py
```

**Item 14.** Open the standalone Fit prototype. On a first visit it shows VB/CB/VB. Select acoustic phonons, set the acoustic scale to 12345, edit its bounds and select **Held**. Switch to acoustic phonons + alloy disorder and back. All three settings follow the shared coefficient. Select acPh, make one band Kane and select S. A two-band model now asks for one relative conductivity prefactor, a three-band model for two. The single Kane model needs none. In a mode with resistivity, each band regains its own dimensional amplitude. Use Tab and Enter on a mode-set lock to read why it is held. Reload the page to reopen the browser draft when local storage is available. The offline replay demonstrates cancellation on composition edits. Real API cancellation, estimator registration and import of a complete v3 file are application acceptance cases.

Run these additional checks from the PR root:

```sh
node docs/superpowers/specs/band-composition-v0.7/evidence/verify_hold_migration.mjs
PYTHONPATH=scripts uv run --frozen python docs/superpowers/specs/band-composition-v0.7/evidence/verify_kane_weights.py
```

The [migration result](evidence/hold-migration.txt) covers per-mode hold decisions, including an untouched active mode and conflicting inactive modes. The [Kane weight result](evidence/kane-weights.txt) compares dimensional and relative thermopower at prescribed filling and includes a nonconducting additional channel. The [current figures](../2026-11-21-band-composition-design.md#12-what-changes-inside-model-and-parameters) show the same default and mixed compositions as the interactive example.

To inspect item 13, enter `0.09` or `0,09` as an edge offset. The field and derived gap both display `0,09`. Repeat with the opposite edge ordering to check the overlap magnitude. Try typing and pasting `1.1` and `1,1` into a valley count. Neither is a valid count, and neither becomes 11. On the band diagram only the energy axis carries numbers.

To inspect item 12, choose DPB, switch between acoustic, disorder and ionized scattering, and compare the absolute field and the Band 2 ratio in Parameters with the Guide. Close a user lock and compare its **Held** caption with the mode-set mass lock in S + ρ. Set a band’s valley count to 2, then try pasting 1,5. Confirm the fractional value cannot enter the model. The numeric diagram check uses $k=0,1$ for a physical displacement of 1 inverse nanometre. The same scale applies to Kane and parabolic bands. Regenerate the current illustrations with `node docs/superpowers/specs/figures/render-reviewed-figures.mjs`. [Conventions and field mapping](../../../../apps/site/src/pages/conventions.mdx#reading-the-proposed-band-composition-labels)

To inspect item 11, choose three parabolic bands in the order VB, CB, VB. Enter 0,10 and 0,04 eV for the two offsets, leave them unlocked and open **Offline fit example**. Select **Start fit example** and advance the three accepted snapshots. Watch the **Band gap** row itself: **Fit…** sits beside the live value. Then select **Return final vector**. The returned gap is 0,075 eV, with CB₂ and VB₁ defining it. The last accepted snapshot gave 0,06 eV with CB₂ and VB₃. Cancel or simulate failure during a new replay to return to the entered values. This deterministic example runs entirely in the browser. The documentation site’s formula-rendering change is proposed in [PR #279](https://github.com/pdasya/seeband-web/pull/279).

To inspect item 10, enter a **Single-valley DOS mass** of 0,209 in Band 1 and set its valley count to 6. **DOS mass (all equivalent valleys)** rounds to 0,690 in units of the free electron mass, matching the p-type bismuth telluride entry in [Jacquot et al., Table I](https://doi.org/10.1007/s11664-009-1059-x). Set the count to 1 to hide the duplicate. Open **Preview · Results and Earlier runs mass labels** for the separate P17 example. The original reported mass of 2 with a saved count of 8 gives a single-valley mass of 0,5. Both previews illustrate the reporting contract. Historical import is specified in [§15.5](../2026-11-21-band-composition-design.md#155-model-results-and-export).

To inspect item 9, select **S** with two or three bands. Parameters shows the persistent caution. With three bands, expand **Example result for a flat profile** below the fields to see the proposed Result status, **Parameters not uniquely determined**. To test the live in-gap cue separately, set the bands to VB, CB, VB, enter offsets of 0,02 and −0,12 eV, and move $E_F$ from 0,01 to 0,03 eV. The in-gap explanation disappears outside the gap while the general caution stays visible. The worked example uses its own synthetic inputs. [Diagnostic criteria in §6.2](../2026-11-21-band-composition-design.md#62-when-a-fit-leaves-a-parameter-undetermined)

To inspect item 8 interactively, start with an acoustic DPB (VB Band 1, CB Band 2). In **Parameters**, enter 0,17 eV for the offset, set bounds of −0,4 and 0,5 eV, and close its lock. Change Band 2 to Kane. The same value, bounds and hold should remain visible. With Band 2 back on Parabolic, change Band 1 to CB and Band 2 to VB. The displayed conduction-minus-valence value becomes −0,17 eV with bounds −0,5 and 0,4 eV, and the lock stays closed. The earlier revision reset the offset to 0,09 eV on the first Kane toggle, cleared both limits and released the hold. [Design contract, §15.4](../2026-11-21-band-composition-design.md#154-lock-manual-value-and-state-persistence) · [Before the fix](https://github.com/pdasya/seeband-web/blob/4e4526c6821d6bf7a06630962b3a7d1bea038acc/docs/superpowers/specs/band-composition-v0.7/fit-guide.html).

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

| ID           | Scope                                                                                                  | Result                                                                                                                                                                                                                                          | Evidence                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| P18-BASE     | P18 archive · domains, transport and explicit DPB fitting                                              | 113 tests passed in the historical checkout.                                                                                                                                                                                                    | [pytest log](evidence/p18-baseline.txt)                             |
| CHARGE       | Shared μ(T), densities and band permutations                                                           | Maximum normalized residual 1.303 × 10⁻¹³.                                                                                                                                                                                                      | [Output](evidence/verify_band_composition_design.txt)               |
| SPB          | Integrals and analytical formulas                                                                      | 36 cases. Maximum Hall error 1.017 × 10⁻¹⁰.                                                                                                                                                                                                     | [Output](evidence/verify_spb_design_coefficients.txt)               |
| DPB-HALL     | P18 archive · core vs. independent formulas                                                            | 27 combinations and 81 temperature points. The Hall error of 1.172 × 10⁻⁶ at CB+CB / dis / 800 K exceeds the proposed 10⁻⁶ tolerance.                                                                                                           | [Inputs and values](evidence/explicit_curves_spb_result.txt)        |
| DPB-HALL-FIX | Published P18 · corrected endpoint quadrature                                                          | Maximum scaled Hall error 5.0771 × 10⁻¹¹, down from 1.1716 × 10⁻⁶ for CB+CB / dis / 800 K.                                                                                                                                                      | [Corrected run](evidence/dpb_hall_p18_fixed.txt)                    |
| SKB          | Acoustic SKB against Tables 1 and 2 of Lin and Liu                                                     | Calculated m_D/mₑ values of 0.952275 and 0.0387615, compared with the published 0.9523 and 0.03877.                                                                                                                                             | [Output](evidence/verify_skb_design_reference.txt)                  |
| SKB-CORE     | All 11 Lin–Liu SKBcal masses with core constants, absolute transport, parabolic limit and valley count | Maximum table error 0.02188%. The 108 synthetic cases cover both charge signs and N = 1, 2, 6. The maximum discrepancy at the exact SPB limit is 1.867 × 10⁻¹¹.                                                                                 | [Per-row results and limits](evidence/verify_skb_core.txt)          |
| S-PROFILE    | Synthetic three-band acoustic S-only                                                                   | Five in-gap energies give identical Seebeck values at three temperatures. Outside-gap probes change the curve at the same nuisance parameters.                                                                                                  | [Numerical results](evidence/three_band_s_profile.txt)              |
| MASS-SCALE   | Two- and three-band parabolic mass identifiability                                                     | 54 common-scale checks. Nearly coincident edges admit 39/39 longitudinal points along a prescribed path. Separated edges admit 3/39 after re-solving the charge balance.                                                                        | [Inputs, gates and results](evidence/mass_identifiability.txt)      |
| MIX          | acPh + dis for parabolic bands                                                                         | 72 cases, both pure-scattering limits and three independent crossover temperatures.                                                                                                                                                             | [Output](evidence/mixed_reference.txt)                              |
| MIX-LEGACY   | Comparison with this PR's math_module at shared μ and integral values                                  | 100, 300 and 800 K. Maximum Hall error 4.495 × 10⁻⁷ for a tolerance of 3 × 10⁻⁵.                                                                                                                                                                | [Branch output](evidence/mixed_legacy_pr.txt)                       |
| MIX-P18      | P18 archive · historical run with --legacy                                                             | The comparison passed in the historical checkout.                                                                                                                                                                                               | [Archived output](evidence/verify_mixed_scattering_design.txt)      |
| UI-FIT-GUIDE | Packaged v0.7 prototype                                                                                | 270 configurations. Checks cover retained settings, the S-only caution, signed in-gap cues and the flat-profile example, both DOS mass conventions, historical conversion and the live gap across fit events, including keyboard use at 320 px. | [Output](evidence/fit-guide-v0.7.txt)                               |
| UI-MODEL     | Earlier Model prototype                                                                                | Checked labels, row counts and Kane restrictions.                                                                                                                                                                                               | [Output](evidence/mock_result.txt)                                  |
| E2E          | New band builder → Parameters → calculate → fit → session                                              | Pending implementation. The full end-to-end matrix of 270 allowed configurations has yet to run.                                                                                                                                                | [Criteria in §1.4 and §8](../2026-11-21-band-composition-design.md) |

## Giving feedback

Include the check ID or section, the claim under review, the inputs, and the expected and observed behavior. Link to the file or primary source. For a proposed feature, specify an acceptance criterion. Agreement between independent calculations supports a formula at the points tested. Interpreting a particular sample still depends on the researcher's physical assumptions.
