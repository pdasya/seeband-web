# DPB convergence correction (P5)

DPB S + ρ and S + ρ + R_H with `acPhDis` must satisfy the convergence check
for both groups: `(m_eff, band_gap, E_F, A, B)` and `(C, D)`. Previously either
group could end the loop independently. A stable C/D pair therefore hid
ongoing changes in the band and scattering parameters, and vice versa.

## Relative changes

For finite nonzero previous values, P5 preserves `abs((current - previous) /
previous)`. It does not introduce a new absolute tolerance or change the
existing threshold. A change equal to the threshold remains acceptable.

- Zero remaining zero has zero change.
- Moving from zero to a nonzero value is not converged.
- Nonfinite values or changes are not converged, including NaN and either infinity.

The check is dimensionless and unchanged by the 300 K conversion of C/D.
Both mixed-scattering groups must pass on the same completed iteration.
The same zero/nonfinite handling protects the existing single-scattering
loops without redesigning their finite-value metric.

## Limits and scientific interpretation

The existing budgets remain 1000 completed iterations for S + ρ and 20 for
S + ρ + R_H. Reaching a budget is reported as `iteration_limit`, not success.
The inherited final Seebeck-only update at the limit is unchanged; #176
tracks the broader stopping rule and consistency of the final model.

Parameter stability at the existing tolerance is not evidence of a good
residual, identifiable material parameters or a global optimum. The separate
acPhDis total-Seebeck grid dependence (#102), collapsed-band behavior,
chemical-potential solver and underflow limitations remain unresolved.
More iterations may expose these limitations instead of repairing them.

Historical desktop golden files remain unchanged. P5 records corrected
expectations separately and tests both group-order failures, zero inputs,
nonfinite changes and the iteration limit. Human physicist confirmation
and parity (#71) remain pending; agent review supplies neither.
