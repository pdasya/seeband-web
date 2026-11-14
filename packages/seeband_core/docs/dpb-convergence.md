# DPB convergence correction (P5)

DPB S + ρ and S + ρ + R_H with `acPhDis` must satisfy the convergence check
for both groups: `(m_eff, band_gap, E_F, A, B)` and `(C, D)`. Previously either
group could end the loop independently. A stable C/D pair therefore hid
ongoing changes in the band and scattering parameters, and vice versa.

## Relative changes

For finite nonzero previous values, P5 preserves `abs((current - previous) /
previous)`. It does not introduce a new absolute tolerance or change the
existing threshold. The computed change passes when it is at most the
threshold. In floating point that is not the same as the exact ratio: B
moving from 1.0 to 1.1 gives 0.10000000000000009, which fails a threshold of
0.1, while 10 to 11 gives 0.1, which passes.

- Zero remaining zero has zero change.
- Moving from zero to a nonzero value is not converged.
- Nonfinite values or changes are not converged, including NaN and either infinity.

The check is dimensionless and unchanged by the 300 K conversion of C/D.
Both mixed-scattering groups must pass on the same completed iteration.
The same zero/nonfinite handling applies to the acPh and dis loops, whose
results on every recorded and demo input are bitwise unchanged. A parameter
value that is not finite ends any DPB loop at once as a failed fit ("not
finite"), as no iteration can settle it; before, a NaN change counted as
converged.

On example 03 from C = 2, D = 0.5, the case #84 cites, the desktop rule stopped
after one iteration in which m_eff changed by +42.6 %, E_F by +25.9 % and A by
+604 %, with S RMSE 5.04 µV/K. At P5, the fit took two iterations and ended within 3e-6 of
the fixed point an outer loop written apart from the core reaches, with S RMSE
3.76 µV/K.

## Limits and scientific interpretation

The existing budgets remain 1000 completed iterations for S + ρ and 20 for
S + ρ + R_H. Reaching a budget is reported as `iteration_limit`, not success.
Through the API, S + ρ cannot reach its budget: 1000 iterations on 03 with
acPhDis took 87.5 s, past the 60 s fit time limit, so a fit that does not
settle ends as `fit_timeout`, with no values. A parameter drifting near 0, or
flipping between two values, now runs to that limit where the desktop rule
stopped after one iteration; this was not seen on real data.
The inherited final Seebeck-only update at the limit is unchanged; #176
tracks the broader stopping rule and consistency of the final model.

Parameter stability at the existing tolerance is not evidence of a good
residual, identifiable material parameters or a global optimum. The separate
collapsed-band behavior and Fermi-integral underflow limitations remain unresolved.
P8 separately repairs the chemical-potential solver; P11 repairs acPhDis
total-Seebeck grid dependence (#102) and changes the numerical fixed point.
More iterations may expose these limitations instead of repairing them.

## What P5 does not fix

At P5, NUM-2 of #84 remained: from E_F = 0, `fsolve` returned μ = 0 with
`ier` = 5 and left the Seebeck stage at its start. The earlier explanation
that this DPB case had no root was incorrect. A valence/conduction pair has
a unique finite-temperature root, including at zero net doping. P8 replaces
this solver and checks conservation; see [the solver contract](chemical-potential.md).
Parameter stability still does not prove that a fit describes measurements,
and the broader stopping/consistency checks of #176 remain separate.

Historical desktop golden files remain unchanged. P5 records corrected
expectations separately and tests both group-order failures, zero inputs,
nonfinite changes and the iteration limit. Human physicist confirmation
and parity (#71) remain pending; agent review supplies neither.

P11 changes the S objective for C ≠ D. The historical P5 fixed-point numbers
above remain evidence for the older formula; current P11 regressions are
recorded separately in `tests/fixtures/physics/p11.json`. Group convergence
checks, budgets, objectives apart from the repaired weight, and fit bounds
are unchanged. See [the pointwise weight correction](dpb-acphdis-weight.md).
