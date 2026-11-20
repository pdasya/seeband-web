---
layout: ../layouts/Prose.astro
title: Results that changed · SeeBand
description: Corrections that change SeeBand Web results compared with the desktop SeeBand, and why.
---

# Results that changed

Core `0.3.0` replaces the public mixed acPhDis option with ionized impurity
power-law transport (lambda=2) for SPB and DPB. S, rho, Hall and electronic
thermal conductivity use the same approximation. Historical mixed results
are not equivalent to the new mechanism. See [the formulas and limitations](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/ionized-impurities.md).

Core `0.2.0` changes the default fitting algorithm to `verified-sequential-v2`.
It preserves staged absolute objectives and physical kernels while correcting
numerical stage solution, consistency and iterative DPB coordinates. Explicit
`legacy-sequential-v1` remains available for reproduction. New and historical
parameter vectors need not agree; numerical convergence, residual adequacy and
parameter identification remain distinct. See [P19/P6](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/verified-sequential-fit.md).

The following corrections change results from earlier web versions. Core
documentation linked below records the formulas, scope and validation evidence.
These are targeted corrections, not claims that every result is physically
valid or matches the desktop.

| Change                                        | Before                                                                                                                                   | After                                                                                                                                            | Evidence                                                                                                                                                                             |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| P2 (#81), DPB Hall prefactor                  | The Hall coefficient used half the corrected prefactor.                                                                                  | At unchanged parameters, R_H doubles. At fixed measured R_H, unconstrained m₁ increases by 2^(2/3) and inferred carrier density doubles.         | [DPB Hall prefactor](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/dpb-hall-prefactor.md)                                                               |
| P3 (#82), acPhDis C and D curve scales        | Derived conductivity, thermal conductivity and per-band curves used inconsistent C and D scales.                                         | Convert dimensionless C and D to temperature scales at 300 K, consistently with resistivity.                                                     | [Curve availability and scale identities](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/curve-availability.md)                                          |
| P4/P12 (#83, #103), SPB Hall                  | SPB S + ρ + R_H was disabled and Hall calculations used stale Fermi energy.                                                              | The mode is enabled; Hall curves and fits use μ(T).                                                                                              | [SPB Hall correction](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/spb-hall-fit.md)                                                                    |
| P5 (#84), DPB acPhDis convergence             | Fits could stop when only one parameter group converged.                                                                                 | Both parameter groups must converge; zero and nonfinite changes are handled explicitly.                                                          | [DPB convergence correction](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/dpb-convergence.md)                                                          |
| P6 (#85), DPB S-only degeneracy               | S-only fitting and drawing applied degeneracy differently to the public mass ratio R.                                                    | Both convert R to the low-level model ratio R/N once; public values and bounds remain in R.                                                      | [DPB S-only degeneracy correction](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/dpb-s-degeneracy.md)                                                   |
| P7 (#86), interpolation support               | Requested fit ranges could generate synthetic interpolation points outside measured temperature coverage.                                | For measurements spanning 25–750 K and a request of 50–800 K, interpolation uses 50–750 K, or 35 points.                                         | [Interpolation support](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/interpolation.md)                                                                 |
| P11 (#102), DPB acPhDis Seebeck               | Every point could use the weight of the final grid temperature.                                                                          | Use the weight at each temperature; total S equals the sum of its weighted band contributions.                                                   | [Pointwise mixed-scattering weight](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/dpb-acphdis-weight.md)                                                |
| P13 (#104), DPB longitudinal weights          | Negative signed mass ratios could produce negative longitudinal weights or NaN.                                                          | Use positive mass-magnitude weights across DPB scattering modes; retain signed carrier density and Hall signs.                                   | [Positive DPB weights](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/dpb-positive-weights.md)                                                           |
| P14 (#105), Fermi integrals in core 0.3.1     | Fermi-integral rounding could make low-temperature transport nonfinite and stop some fits.                                               | Stable moments preserve dilute-band ratios and symmetric Hall cancellation. The revised density solve and derivatives change some fit endpoints. | [P14 comparisons and limits](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/golden-results.md#stable-fermi-integrals-p14)                                |
| P16 (#107), held-E_F gap search in core 0.3.2 | A Seebeck-stage gap fit from its upper bound with E_F held could stop at the bound or in the onset layer below it, or fail at E_F = E_g. | The bounded gap interval is searched first with the true objective; the derivative at E_F = E_g uses the equal one-sided plateau limit.          | [Gap fitted with the Fermi energy held](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/verified-sequential-fit.md#gap-fitted-with-the-fermi-energy-held) |

Core `0.1.0` includes the landed P2–P7 corrections listed above. Core `0.1.1` additionally includes P8: a checked signed chemical-potential
solve, stable negative F₁/₂ tail and rejection of analytically invalid optimizer
trial points. Invalid starts and uncertifiable density roots fail explicitly.
P14 addresses the transport underflow that remained after P8. See the
[P14 validation](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/golden-results.md#stable-fermi-integrals-p14)
and the
[solver contract](https://github.com/pdasya/seeband-web/blob/main/packages/seeband_core/docs/chemical-potential.md).
Core `0.1.2` adds P9: neural-net selection uses the actual minimum and maximum
temperatures, and paired rows are sorted on a copy before preparing the input.
Direct callers sending unsorted rows can receive a net or a different net
compared with earlier versions. Parsed web uploads are already sorted, so
this correction leaves their initial values unchanged. Estimates remain
starting values without a known error bar; no measurements are removed or
averaged.

Core `0.1.3` adds P11: total DPB mixed-scattering Seebeck uses its pointwise
band weight in the fit, curve and RMSE paths. Other numerical and model
limitations remain. The evidence linked above records changed example fits.

Core `0.1.4` adds P13's positive longitudinal DPB weights and branch-preserving
fit bounds. Physical-limit tests and synthetic fit recoveries cover both mass signs. Neural guesses are not validated for every corrected
branch.

P10 adds result-version and provenance metadata only; it does not change
formulas or fitting. Core version `0.1.0` is the first traceable version.
Earlier results reporting `0.0.0` may represent different corrected states,
and a missing version remains unknown. Human physicist confirmation and the
desktop parity gate (#71) remain open. Author review #80 was closed at the
project owner’s request; author contact and confirmation remain pending.
No sample-specific fitting claim is made here.
