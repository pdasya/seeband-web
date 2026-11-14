# Changelog

## Unreleased

- P11 (#102), core 0.1.1: apply the acPhDis band weight at each temperature
  in total DPB Seebeck, consistently with the weighted band contributions.
  Fit objectives, plotted curves and RMSE now use the same pointwise formula;
  C/D units, scattering laws, fit weights, bounds and stop thresholds are
  unchanged. Remove the repaired warning, preserve original desktop/P8
  evidence and record changed mixed-scattering results separately. This
  branch depends on P8 for checked grid-independent chemical potentials.
  Human physicist confirmation, parity and author review remain pending.

- P8 (#87): solve the signed carrier balance with a bracketed method in
  reduced chemical potential, check the normalized residual at every
  temperature, and restore the input order after sorting and deduplication.
  All SPB/DPB transport and Fermi-integral paths use the same checked solve.
  Invalid domains and failed conservation checks now fail explicitly instead
  of silently using an unconverged number. The DPB E_F = 0 case has a finite
  solution; its former stuck-at-start behavior was a solver error.
  Historical desktop captures remain unchanged, with separate P8 regression
  expectations. Fermi-integral approximations, fit objectives, weights and
  bounds are unchanged; physical validity and human confirmation remain
  separate from numerical convergence.

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
  that is not finite now fails the fit at once. At P5, NUM-2 of #84
  remained; P8 subsequently repairs the chemical-potential solver behind the
  E_F = 0 stuck-stage symptom. The broader fit checks of #176 remain separate.

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
