# Known issues

Core 0.3.0 removes acPhDis from public choices. The P3/P11 notes below describe
historical corrections, not current availability. The ionized impurity option
uses a separate approved power-law model; see [its assumptions](ionized-impurities.md).

`known_issues.py` records active limitations so users can interpret affected
results. Corrections remove only the issue they resolve; other limitations
remain listed until they are separately fixed and validated.

- `FitMode.known_issues` lists what applies to a mode, in descriptions. `FitMode.disabled` says that a client must not offer it.
- `known_issues` on a `FitResult` or `CurveResult` lists the ids that apply to that result, with their conditions checked. A failed fit lists only a disabled mode.
- `columns` on an entry names the curves of a kind it changes, so that a client can mark the right one.
- A client shows `known_issue.<id>` through i18n. `explanation` is for developers, and must not reach users.
- **A curve's flags describe its formula, not its parameters.** Parameters from a flagged fit carry that fit's error into every curve drawn from them. So a client showing a curve from a fit must show the flags of both.

To remove a flag once its error is fixed, delete its entry and its row here, and its i18n text. Tests that name it then fail, on purpose, and `tests/test_known_issues.py` also checks some of the errors themselves, so that a fix prompts removing the flag.

| Id                           | Severity   | Where                                                                                              | Fixed by |
| ---------------------------- | ---------- | -------------------------------------------------------------------------------------------------- | -------- |
| `dpb_loop_degeneracy`        | caution    | explicit legacy iterative DPB fits, when N2/N1 is not 1                                            | #85      |
| `collapsed_m_eff`            | unreliable | DPB, when m_eff is near 0, as on `02_SiP` (D19)                                                    | #107     |
| `no_chemical_potential`      | unreliable | SPB, when the Fermi energy is outside the band                                                     | #106     |
| `hall_dis_no_reference`      | caution    | DPB S + ρ + R_H with `dis`. This is a missing reference, not an error: the desktop fails here (D1) | #71      |
| `band_diagram_formula`       | caution    | the sketch of E(k), in `band_diagram` alone, and in no fit or curve                                | #108     |
| `interpolation_extrapolates` | unreliable | any result, when `extrapolated` is set on its request                                              | #86      |

`affects_band_diagram` puts an entry on the sketch of E(k) alone, through `band_diagram_issue_ids`.

P7 (#86) limits new interpolation to measured support and reports a limited
range separately. `interpolation_extrapolates` is retained for legacy or
external data explicitly marked `extrapolated` by the caller; the repaired
server interpolation no longer emits that provenance flag itself.

The caller sets `extrapolated`, from `InterpolatedData`, since a fit does not know where its data came from.

The DPB Hall-prefactor flag was removed by [P2](dpb-hall-prefactor.md), which corrects the coefficient in all three scattering modes.

P3 (#82) removes the acPhDis curve-scale flag: derived curves now convert the dimensionless 300 K ratios C and D to temperature scales consistently with resistivity. P11 separately repairs the grid-dependent total-Seebeck weight (#102).

P6 fixes the S-only part of #85: fitting and drawing now pass the same internal mass R/N to the numerical model. The S-only mismatch flag is removed. P19 completes the iterative-mode coordinate correction for `verified-sequential-v2`; `dpb_loop_degeneracy` remains a caution for explicit legacy fits. See [the mass convention and validation](dpb-s-degeneracy.md).

P13 removes `negative_m_eff_weight` and corrects the longitudinal DPB mass
weights to use |r| in every scattering mode. Signed carrier density and Hall
signs remain. P13 alone did not fix iterative nonunit-degeneracy fits, collapsed
bands or Fermi-integral underflow; see [positive DPB weights](dpb-positive-weights.md).

P5 (#84) removes the early-stop flag: DPB mixed-scattering fits now require both parameter groups to converge and handle zero/nonfinite changes explicitly. See [the convergence correction](dpb-convergence.md). P11 separately fixes #102; neither correction supplies human physicist confirmation.

P4/P12 (#83, #103) remove the SPB Hall disabled-mode and stale-Fermi-energy flags after repairing the fit scales and using μ(T) in Hall integrals. See [the correction and synthetic validation](spb-hall-fit.md). Human physicist confirmation remains pending.

## What is not here

- **Disabled is a flag.** The API refuses any mode carrying a disabled issue with a 409. No current mode carries one after P4/P12.
- **F₀ underflowing (#105)** gives NaN or infinity at low temperatures with large gaps, which a client can see as non-finite values. The flag would need the result, not its inputs.
- **E_F inside the gap (#107)** cannot be told from a good fit by its inputs alone, and `at_bounds` and `parameter_errors` report part of it.
- **`underdetermined` interpolation** has no issue that fixes it, because it describes the data. `InterpolatedData` reports it.
- **Neural-net range selection (P9)** now uses actual Tmin/Tmax and sorts paired input rows before inference. The parser already sorts files (D22), and direct `POST /api/guess` callers now get the same range and prediction for reordered distinct-temperature rows. `unsorted_temperature` remains input provenance. It belongs to no mode, so it is not a registry entry.
- **Missing desktop coverage (#71)** remains open, including the desktop/web
  parity gate; corrected web results do not establish desktop parity.

P8 (#87) checks density roots before transport. An uncertifiable density root
fails the calculation request (HTTP 422) or fit explicitly; no partial array
is used. In DPB with two valence bands, `E_F ≥ max(0, E_g)` gives no finite
root. The calculation API reports the corresponding `chemical_potential_*`
error detail for each unsupported domain (#106). The SPB
`no_chemical_potential` registry ID is retained for interpretation of flagged
fit results and exports. Successful density checks do not prevent the separate F₀ transport
cancellation/underflow (#105), which can still produce nonfinite curve points.
Invalid optimizer trial domains are rejected separately from numerical failures;
invalid starts still fail. See [the solver contract](chemical-potential.md).

P11 (#102) removes `acphdis_band_weight`: total DPB acPhDis Seebeck now
uses each temperature's weight, as the band contributions already did.
P8 supplies grid-independent checked roots. Iterative nonunit degeneracy,
final-stage fit consistency and physical acceptance remain separate. See
[the correction and evidence](dpb-acphdis-weight.md) and the later
[P13 positive-weight correction](dpb-positive-weights.md).

Core0.2.0's verified-sequential-v2 completes the P6 public-coordinate correction
and omits dpb_loop_degeneracy on its fit results. The registry entry remains
for explicit legacy-sequential-v1 reproduction. Small-mass warnings remain
heuristic inference cautions, not a mass floor or proof that a channel vanished.
Verified diagnostics separately report numerical checks and detected structural
nonidentifiability; absence of a structural warning is not a full P23 analysis.
See [verified sequential fitting](verified-sequential-fit.md).
