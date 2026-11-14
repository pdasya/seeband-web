# Changelog

## Unreleased

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
  gives the result a sorted file does; a Hall point beyond the reach of the
  Fermi integrals (μ/T above 700) is NaN rather than a failed curve; and a
  start mass of 0, on an empty branch, or of the wrong sign for R_H fails with
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
