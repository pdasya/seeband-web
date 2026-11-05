# Known issues

The first stage ports the desktop exactly, so its errors stay until the Physics fixes stage. `known_issues.py` records them, so that users see them and do not take doubtful numbers as sound.

- `FitMode.known_issues` lists what applies to a mode, in descriptions. `FitMode.disabled` says that a client must not offer it.
- `known_issues` on a `FitResult` or `CurveResult` lists the ids that apply to that result, with their conditions checked.
- A client shows `known_issue.<id>` through i18n. `explanation` is for developers.

To remove a flag once its error is fixed, delete its entry. Every entry names the issue that removes it.

| Id                           | Severity   | Where                                                                     | Fixed by |
| ---------------------------- | ---------- | ------------------------------------------------------------------------- | -------- |
| `spb_hall_mode_disabled`     | disabled   | SPB S + ρ + R_H                                                           | #83      |
| `spb_hall_uses_fermi_energy` | unreliable | R_H and the fit in SPB S + ρ + R_H                                        | #103     |
| `dpb_hall_prefactor`         | unreliable | R_H, m1, and n from it in DPB S + ρ + R_H                                 | #81      |
| `acphdis_conductivity_scale` | unreliable | σ and κ with acPhDis, SPB and DPB                                         | #82      |
| `acphdis_band_weight`        | unreliable | S with acPhDis in DPB S + ρ and S + ρ + R_H                               | #102     |
| `acphdis_early_stop`         | caution    | fits with acPhDis in those modes                                          | #84      |
| `dpb_s_degeneracy`           | unreliable | DPB S, when N2/N1 is not 1                                                | #85      |
| `negative_m_eff_weight`      | caution    | DPB, when m_eff is below 0. This may be intended, and a physicist decides | #104     |
| `hall_dis_web_bounds`        | caution    | DPB S + ρ + R_H with `dis`, which has no desktop reference (D1)           | #71      |
| `interpolation_extrapolates` | unreliable | any mode, when interpolation made up points                               | #86      |

## What is not here

- **Disabled is a flag.** The model still runs `spb_s_rho_rh`, because tests and V1 need it. A8 must refuse it, and the API must not offer it.
- **Errors at unusual inputs,** such as F₀ underflowing (#105), no chemical potential for a Fermi energy outside the band (#106) and parameters the data do not determine (#107), have no entry. They depend on results that `status`, `at_bounds` and `parameter_errors` report in part.
- **The Conventions page** does not exist yet, so S3 takes its note on known issues from this list.
