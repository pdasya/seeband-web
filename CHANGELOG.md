# Changelog

## Unreleased

- P4/P12 (#83, #103): enable SPB S + ρ + R_H after correcting signed
  mass initialization, bounds and recovery, the mass control scale, and the
  mixed-scattering C return scale at 300 K. SPB Hall curves and fits now use
  the chemical potential at each temperature, conserving carrier density.
  Hall factors recover the degenerate limit 1 and nondegenerate limit 3π/8.
  Synthetic regression results replace no historical desktop captures.
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
