# Changelog

## Unreleased

- P5 (#84): require both parameter groups to converge in DPB acPhDis fits.
  Zero-valued parameters no longer cause division by zero, and nonfinite
  changes cannot be reported as converged. Unchanged zeros have zero change;
  leaving zero requires another iteration. Preserve historical desktop
  captures and record corrected fit expectations separately. The independent
  acPhDis Seebeck grid-dependence issue (#102) remains flagged.

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
