# Changelog

## Unreleased

- Core `0.3.0`: replace public acPhDis with ionized impurity scattering for
  SPB and DPB, including S-only. Use the approved tau(E) proportional to E^(3/2)
  approximation with lambda=2, consistent longitudinal, Hall and electronic
  thermal moments, and explicit immutable scattering exponents. Retain acPh/dis
  behavior and historical mixed-scattering captures. Ionized fits require
  Verified; SPB estimates follow scattering and DPB neural estimates are
  unavailable for this mechanism. See [the model contract](packages/seeband_core/docs/ionized-impurities.md).

- Reuse certified chemical potentials for exact repeated physical inputs within
  a verified fit. Preserve prediction budgets and fresh terminal audits. Avoid
  duplicate demo/API fits in tests while retaining their assertions; run golden,
  core and API CI test groups independently behind the required Python gate.

- Allow 180 seconds by default for API fits, configurable as before, after
  verified demo fitting exceeded 60 seconds on hosted Linux. Concurrency and
  input limits remain in force; numerical certification criteria are unchanged.

- P19/P6 (#176, #85), core `0.2.0`: default to `verified-sequential-v2`;
  preserve `legacy-sequential-v1` by explicit selection. Profile free inverse
  amplitudes, scale and validate remaining stage derivatives, and check
  conditional optimality at the same final vector. Verified DPB fitting uses
  public R coordinates and converts R/N once at evaluation. Preserve staged
  absolute objectives, physical kernels, input data, user bounds and held values.
  Add algorithm provenance and numerical/consistency/residual/identifiability
  diagnostics across API, session and exports. Numerical settlement does not
  establish physical adequacy or uncertainty. Built-in preview RMSE evaluates
  directly at measured temperatures; pointwise percentages are unavailable at
  measured rho/Hall zeros. See [verified sequential fitting](packages/seeband_core/docs/verified-sequential-fit.md).

- P13 (#104), core `0.1.4`: use positive mass-magnitude weights for
  longitudinal DPB transport in S-only, single-scattering and mixed-scattering
  modes, including band contributions. Keep signed mass coordinates, carrier
  density and Hall carrier signs; Hall uses the corrected resistivity. DPB fits
  retain the signed-start branch, exclude zero without adding a mass floor, and
  intersect bounds with that branch. Density solving, fit objectives and
  tolerances are unchanged. Remove `negative_m_eff_weight`; P6 iterative
  nonunit-degeneracy bounds, P16/P19, and numerical underflow remain open.
  P18 explicit band types and CB+CB are deferred. Focused physical-limit tests and synthetic fit recoveries cover both mass
  signs. These checks are not measurements or validation of neural guesses. Human physicist
  confirmation and desktop parity remain separate release gates. See
  [positive DPB weights](packages/seeband_core/docs/dpb-positive-weights.md).

- P11 (#102), core `0.1.3`: retain the temperature-dependent acPhDis band
  weight in total DPB Seebeck, consistently with the weighted band contributions.
  Fits, curves and RMSE use the corrected pointwise expression. C/D conversion,
  least-squares residual scales, bounds and stopping thresholds are unchanged.
  Remove only `acphdis_band_weight`; preserve desktop/P8 evidence and record
  affected results separately. Restore the independent example-03 outer-loop
  check. Human scientific acceptance and desktop parity remain separate.

- P9 (#88), core `0.1.2`: choose the DPB neural network from the actual minimum and
  maximum temperatures, then sort paired temperature/Seebeck rows before
  preparing its input. Reversed or shuffled distinct-temperature rows now use
  the same network and prediction as sorted data. Keep the unsorted-input provenance warning,
  with corrected wording. Legacy no-net first/last fields now report actual
  minimum/maximum coverage. Network weights, range priority, polynomial
  degree and fit criteria are unchanged. Preserve original desktop captures
  and record the corrected reversed-row expectation separately.

- P8 (#87), core `0.1.1`: solve the signed carrier balance independently at
  each temperature with a checked bracketed method. Use the same negative-tail
  Fermi approximation in a stable algebraic form. Reject analytically invalid
  optimizer trial points without hiding numerical failures at valid parameters;
  invalid starts and uncertifiable density roots still fail explicitly. Keep
  desktop compatibility tests alongside separate P8 regression expectations.
  No bounds, fit weights or conservation tolerance are relaxed.

- Documentation review: correct the signed SPB Hall cutoff and clarify DPB
  convergence timing, interpolation coverage, degeneracy cancellation and the
  open negative-weight interpretation. No calculation behavior changed.

- P10: expose the installed `seeband_core` version (`0.1.0`) in health,
  calculation and fit API responses, and record separate server, fit and curve
  provenance in shared export headers. This is result metadata only; it changes
  no formulas or fit behavior. Older results without a recorded version remain
  unknown and are not assigned a version retroactively. This is not release
  approval; scientific confirmation and the desktop parity work remain open.

- FS18: preserve a conductivity file's source quantity when requesting
  interpolation without an explicit column mapping. Explicit mappings and
  chosen units remain in use. Browser regressions cover conductivity upload,
  headerless column choice, S/cm units and the resistivity sent to a fit.

- P7 (#86): evaluate interpolation only on the overlap of each quantity's
  measured temperature range and the requested fit range. Unsupported or
  too-short overlaps fail explicitly instead of extrapolating synthetic
  points into the fit. Show when measured coverage limits the range; retain
  legacy extrapolation provenance warnings. The polynomial degree and fit
  criteria are unchanged, with separate corrected regression expectations.
  An overlap the data narrow needs 40 K, so that the grid has two points;
  each refusal says why (`interpolation_failure_reasons`); a window with no
  measured point says that the polynomial alone sets it; and results and
  exports name the range a fit used.

- P6 (#85, S-only scope): use the same degeneracy-weighted mass in DPB S
  fitting and drawing. Public mass coordinates, bounds and uncertainties
  stay unchanged; the low-level model receives R/N on both paths. Add
  nonunit-degeneracy synthetic regression results and remove only the
  S-only mismatch warning. The iterative-mode mass/bounds warning remains.

- P5 (#84): require both parameter groups to converge in DPB acPhDis fits.
  Zero-valued parameters no longer cause division by zero, and nonfinite
  changes cannot be reported as converged. Unchanged zeros have zero change;
  leaving zero requires another iteration. Preserve historical desktop
  captures and record corrected fit expectations separately. The independent
  acPhDis Seebeck grid-dependence issue (#102) remains flagged. A parameter
  that is not finite now fails the fit at once. NUM-2 of #84 is not fixed: a
  fit from E_F = 0 still converges at its start values (#106, #176).

- P4/P12 (#83, #103): enable SPB S + ρ + R_H after correcting signed
  mass initialization, bounds and recovery, the mass control scale, and the
  mixed-scattering C return scale at 300 K. SPB Hall curves and fits now use
  the chemical potential at each temperature, conserving carrier density.
  Hall factors recover the degenerate limit 1 and nondegenerate limit 3π/8.
  Synthetic regression results replace no historical desktop captures.
  Every fit now sorts its points by temperature, so an API client's order
  gives the result a sorted file does; a Hall point with signed reduced
  potential x = sign(m) μ(T)/T above 700 is NaN rather than a failed curve;
  a start mass of 0, on an empty branch, or of the wrong sign for R_H fails with
  its reason. The band-mass error is conditional on E_F.
  Human physicist confirmation and parity/author review remain pending;
  enabling this mode is not scientific release approval.

- P3 (#82): convert acPhDis C and D from dimensionless ratios at 300 K
  to temperature scales in SPB/DPB conductivity, thermal conductivity and
  per-band curves, consistently with resistivity. Corrected σρ equals 1.
  Remove the obsolete scale warning and add corrected golden expectations.
  The separate grid-dependent total-Seebeck error (#102) remains flagged.

- P2 (#81): correct the DPB Hall prefactor for acPh, dis and acPhDis.
  R_H doubles at fixed parameters. At fixed measured R_H, unconstrained m₁
  increases by 2^(2/3) and inferred carrier density doubles. Regenerate the
  synthetic demo and remove the `dpb_hall_prefactor` warning. Original desktop
  captures are preserved, with separate P2 regression expectations.

- Initial guess now targets the selected SPB or DPB model. SPB estimates its
  Fermi energy numerically from S(T), preserves absolute mass magnitude, and
  chooses the carrier sign. Previously, automatic loading always guessed DPB
  and the SPB button was unavailable. DPB network weights and predictions are
  unchanged. The API adds `numerical_guess` as an initial-guess response.
