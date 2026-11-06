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
| `spb_hall_mode_disabled`     | disabled   | every result of SPB S + ρ + R_H                                                                    | #83      |
| `spb_hall_uses_fermi_energy` | unreliable | R_H and the fit in SPB S + ρ + R_H                                                                 | #103     |
| `dpb_hall_prefactor`         | unreliable | R_H, m1, and n from m1 in DPB S + ρ + R_H                                                          | #81      |
| `acphdis_curve_scale`        | unreliable | σ, κ and S by band with acPhDis, SPB and DPB                                                       | #82      |
| `acphdis_band_weight`        | unreliable | S with acPhDis in DPB S + ρ and S + ρ + R_H                                                        | #102     |
| `acphdis_early_stop`         | unreliable | fits with acPhDis in those modes                                                                   | #84      |
| `dpb_s_degeneracy`           | unreliable | all of DPB S, when N2/N1 is not 1                                                                  | #85      |
| `dpb_loop_degeneracy`        | caution    | fits in the other DPB modes, when N2/N1 is not 1                                                   | #85      |
| `negative_m_eff_weight`      | caution    | DPB, when m_eff is below 0. This may be intended, and a physicist decides                          | #104     |
| `collapsed_m_eff`            | unreliable | DPB, when m_eff is near 0, as on `02_SiP` (D19)                                                    | #107     |
| `no_chemical_potential`      | unreliable | SPB, when the Fermi energy is outside the band                                                     | #106     |
| `hall_dis_no_reference`      | caution    | DPB S + ρ + R_H with `dis`. This is a missing reference, not an error: the desktop fails here (D1) | #71      |
| `interpolation_extrapolates` | unreliable | any result, when `extrapolated` is set on its request                                              | #86      |

The caller sets `extrapolated`, from `InterpolatedData`, since a fit does not know where its data came from.

## What is not here

- **Disabled is a flag.** The model still runs `spb_s_rho_rh`, because tests and V1 need it. The API refuses it with a 409, and does not offer it.
- **F₀ underflowing (#105)** gives NaN or infinity at low temperatures with large gaps, which a client can see as non-finite values. The flag would need the result, not its inputs.
- **No chemical potential in DPB (#106)** has no simple condition on the inputs, unlike SPB.
- **E_F inside the gap (#107)** cannot be told from a good fit by its inputs alone, and `at_bounds` and `parameter_errors` report part of it.
- **`underdetermined` interpolation** has no issue that fixes it, because it describes the data. `InterpolatedData` reports it.
- **Choosing a net by the first and last rows (P9)** does not reach this path, because the parser sorts (D22). A client can send `POST /api/guess` unsorted rows, and its answer then carries the warning `unsorted_temperature`. It belongs to no mode, so it is not an entry here.
- **The band diagram (#108)** belongs to no mode, so a client must treat it with care until then.
- **D4 asks to flag acPhDis results.** In core units, S and ρ of SPB use one scale, so only `acphdis_curve_scale` applies.
- **The Conventions page** does not exist yet, so S3 takes its note on known issues from this list.
