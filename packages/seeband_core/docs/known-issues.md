# Known issues

The first stage ports the desktop exactly, so its errors stay until the Physics fixes stage. `known_issues.py` records them, so that users see them and do not take doubtful numbers as sound.

- `FitMode.known_issues` lists what applies to a mode, in descriptions. `FitMode.disabled` says that a client must not offer it.
- `known_issues` on a `FitResult` or `CurveResult` lists the ids that apply to that result, with their conditions checked. A failed fit lists only a disabled mode.
- `columns` on an entry names the curves of a kind it changes, so that a client can mark the right one.
- A client shows `known_issue.<id>` through i18n. `explanation` is for developers, and must not reach users.
- **A curve's flags describe its formula, not its parameters.** Parameters from a flagged fit carry that fit's error into every curve drawn from them. So a client showing a curve from a fit must show the flags of both.

To remove a flag once its error is fixed, delete its entry and its row here, and its i18n text. Tests that name it then fail, on purpose, and `tests/test_known_issues.py` also checks some of the errors themselves, so that a fix prompts removing the flag.

| Id                           | Severity   | Where                                                                                              | Fixed by |
| ---------------------------- | ---------- | -------------------------------------------------------------------------------------------------- | -------- |
| `acphdis_band_weight`        | unreliable | S with acPhDis in DPB S + ρ and S + ρ + R_H                                                        | #102     |
| `dpb_loop_degeneracy`        | caution    | fits in the other DPB modes, when N2/N1 is not 1                                                   | #85      |
| `negative_m_eff_weight`      | caution    | DPB, when m_eff is below 0. This may be intended, and a physicist decides                          | #104     |
| `collapsed_m_eff`            | unreliable | DPB, when m_eff is near 0, as on `02_SiP` (D19)                                                    | #107     |
| `no_chemical_potential`      | unreliable | SPB, when the Fermi energy is outside the band                                                     | #106     |
| `hall_dis_no_reference`      | caution    | DPB S + ρ + R_H with `dis`. This is a missing reference, not an error: the desktop fails here (D1) | #71      |
| `band_diagram_formula`       | caution    | the sketch of E(k), in `band_diagram` alone, and in no fit or curve                                | #108     |
| `interpolation_extrapolates` | unreliable | any result, when `extrapolated` is set on its request                                              | #86      |

`affects_band_diagram` puts an entry on the sketch of E(k) alone, through `band_diagram_issue_ids`.

The caller sets `extrapolated`, from `InterpolatedData`, since a fit does not know where its data came from.

The DPB Hall-prefactor flag was removed by [P2](dpb-hall-prefactor.md), which corrects the coefficient in all three scattering modes.

P3 (#82) removes the acPhDis curve-scale flag: derived curves now convert the dimensionless 300 K ratios C and D to temperature scales consistently with resistivity. The independent grid-dependent total-Seebeck error (#102) remains flagged.

P6 fixes the S-only part of #85: fitting and drawing now pass the same internal mass R/N to the numerical model. The S-only mismatch flag is removed. The separate iterative-mode mass/bounds caution (`dpb_loop_degeneracy`, also tracked by #85) remains unresolved. See [the mass convention and validation](dpb-s-degeneracy.md).

P5 (#84) removes the early-stop flag: DPB mixed-scattering fits now require both parameter groups to converge and handle zero/nonfinite changes explicitly. See [the convergence correction](dpb-convergence.md). This does not fix #102 or replace human physicist confirmation.

P4/P12 (#83, #103) remove the SPB Hall disabled-mode and stale-Fermi-energy flags after repairing the fit scales and using μ(T) in Hall integrals. See [the correction and synthetic validation](spb-hall-fit.md). Human physicist confirmation remains pending.

## What is not here

- **Disabled is a flag.** The API refuses any mode carrying a disabled issue with a 409. No current mode carries one after P4/P12.
- **F₀ underflowing (#105)** gives NaN or infinity at low temperatures with large gaps, which a client can see as non-finite values. The flag would need the result, not its inputs.
- **No chemical potential in DPB (#106)** has no simple condition on the inputs, unlike SPB.
- **E_F inside the gap (#107)** cannot be told from a good fit by its inputs alone, and `at_bounds` and `parameter_errors` report part of it.
- **`underdetermined` interpolation** has no issue that fixes it, because it describes the data. `InterpolatedData` reports it.
- **Neural-net range selection (P9)** now uses actual Tmin/Tmax and sorts paired input rows before inference. The parser already sorts files (D22), and direct `POST /api/guess` callers now get the same range and prediction for reordered distinct-temperature rows. `unsorted_temperature` remains input provenance. It belongs to no mode, so it is not a registry entry.
- **The Conventions page** does not exist yet, so S3 takes its note on known issues from this list.
