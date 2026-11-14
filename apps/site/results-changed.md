# Results that changed

The following corrections change results from earlier web versions. Core
documentation linked below records the formulas, scope and validation evidence.
These are targeted corrections, not claims that every result is physically
valid or matches the desktop.

| Change                                 | Before                                                                                                    | After                                                                                                                                    | Evidence                                                                                          |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| P2 (#81), DPB Hall prefactor           | The Hall coefficient used half the corrected prefactor.                                                   | At unchanged parameters, R_H doubles. At fixed measured R_H, unconstrained m₁ increases by 2^(2/3) and inferred carrier density doubles. | [DPB Hall prefactor](../../packages/seeband_core/docs/dpb-hall-prefactor.md)                      |
| P3 (#82), acPhDis C and D curve scales | Derived conductivity, thermal conductivity and per-band curves used inconsistent C and D scales.          | Convert dimensionless C and D to temperature scales at 300 K, consistently with resistivity.                                             | [Curve availability and scale identities](../../packages/seeband_core/docs/curve-availability.md) |
| P4/P12 (#83, #103), SPB Hall           | SPB S + ρ + R_H was disabled and Hall calculations used stale Fermi energy.                               | The mode is enabled; Hall curves and fits use μ(T).                                                                                      | [SPB Hall correction](../../packages/seeband_core/docs/spb-hall-fit.md)                           |
| P5 (#84), DPB acPhDis convergence      | Fits could stop when only one parameter group converged.                                                  | Both parameter groups must converge; zero and nonfinite changes are handled explicitly.                                                  | [DPB convergence correction](../../packages/seeband_core/docs/dpb-convergence.md)                 |
| P6 (#85), DPB S-only degeneracy        | S-only fitting and drawing applied degeneracy differently to the public mass ratio R.                     | Both convert R to the low-level model ratio R/N once; public values and bounds remain in R.                                              | [DPB S-only degeneracy correction](../../packages/seeband_core/docs/dpb-s-degeneracy.md)          |
| P7 (#86), interpolation support        | Requested fit ranges could generate synthetic interpolation points outside measured temperature coverage. | For measurements spanning 25–750 K and a request of 50–800 K, interpolation uses 50–750 K, or 35 points.                                 | [Interpolation support](../../packages/seeband_core/docs/interpolation.md)                        |

Core `0.1.0` includes the landed P2–P7 corrections listed above. P8 and P9
remain separate pending changes and are not included in this version note.

P10 adds result-version and provenance metadata only; it does not change
formulas or fitting. Core version `0.1.0` is the first traceable version.
Earlier results reporting `0.0.0` may represent different corrected states,
and a missing version remains unknown. Human physicist confirmation and the
desktop parity gate (#71) remain open; author review #80 remains open as well.
No sample-specific fitting claim is made here.
