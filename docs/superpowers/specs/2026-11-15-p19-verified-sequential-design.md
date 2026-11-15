# P19 verified sequential fitting

Approved by the owner on 2026-11-15: make the corrected sequential algorithm the
default, preserve `legacy-sequential-v1` by explicit selection, and include the
remaining P6 coordinate correction. Do not merge.

## Contract

- New identifier: `verified-sequential-v2`; default for core and API requests.
  Legacy routes retain the core 0.1.4 algorithm, arithmetic and historical tests.
  No automatic fallback from an unsuccessful verified fit to legacy success.
- Preserve P13 physical kernels and carrier branch, P8 certified density and its
  distinction between invalid trials and numerical failures, measurements,
  user bounds, held values and staged absolute least-squares objectives.
  Joint S/rho/Hall weighting remains P22.
- Verified fitting uses public R throughout optimization, bounds, covariance
  coordinates and callbacks; convert r=R/N only at kernel evaluation. Legacy
  retains its documented P6 limitation for reproducibility.
- Profile free reciprocal rho amplitudes exactly within transformed original
  bounds; similarly handle a free inverse Hall amplitude. Held amplitudes are
  unchanged. Singular zero endpoints and zero-information shapes are explicit.
- Scale remaining coordinates and validate finite-difference derivatives in
  the admissible domain. Retain solver termination/optimality/evaluation data.
  Neither a small parameter step nor an unchanged start proves convergence.
- Check conditional stage optimality at the same final parameter vector. If a
  rho update changes S, continue the complete sweep. Detect stalls/cycles and
  enforce a shared finite budget; use bounded deterministic recovery for flat
  starts only within user bounds and the selected carrier branch.
- Distinguish numerical termination, stage consistency, residual adequacy and
  identifiability. Final residual aggregates use measured temperatures and the
  exact returned parameters. Zero signals have absolute RMSE and a nullable
  relative L2 metric. No invented physical goodness threshold or chi-square.
- Do not invent unique hidden-band parameters or a mass floor. Conditional
  profiling must not create zero error bars. New-route uncertainty remains
  not assessed unless independently justified; full P23 inference is separate.

## Interfaces

Append `algorithm` to FitRequest with default `verified-sequential-v2`.
Append algorithm and optional typed diagnostics to FitResult; legacy results
must be labelled explicitly. Diagnostics carry termination, stage consistency,
stage objectives/optimality, evaluations/recoveries, residual aggregates and
unidentified parameter names, with residual adequacy and uncertainty marked
not assessed. Preserve existing status values where possible; `stalled` may
be added for a usable nonconverged endpoint, including a cycle reason.

Core owns all mathematics. API validates the algorithm and serializes typed
diagnostics; generated client types are regenerated. Web exposes explicit
legacy selection, keeps it in request/cache identity and saved sessions, and
shows numerical diagnostics distinctly from physical fit validity. Old results
without algorithm provenance remain unknown rather than being relabelled.

## Evidence and acceptance

Reproductions live outside the checkout at /private/tmp/p19-_-probe._ and the
analysis report P19-numerical-proposal-2026-11-15.md. Synthetic fixed-amplitude
legacy error 15.98% must be corrected to numerical precision under the same
objective; ordinary synthetic outer-loop S-SSE 1235.87 vs conditional 0.6102
must not be accepted as final convergence. Include SiP and D1 measured-point
aggregate regressions without sample-dependent code or forced fit quality.

Cover all applicable SPB/DPB modes/scattering, both supported branches, N=1
and nonunit N, free/held variables, zero-permitted shape parameters, custom
and active bounds, compensated Hall, intrinsic and one-channel limits,
invalid density starts/trials and valid numerical failures. Validate derivatives,
parameter recovery only in identifiable cases, final residual/curve agreement,
budget/callback handling, legacy parity and algorithm provenance round trips.

## Alternatives

Only tightening tolerances or x_scale is insufficient in the reproduced case.
Fully numerical amplitude fitting with analytic Jacobians is possible, but
exact conditional profiling removes an unnecessary nonlinear direction.
Joint fitting changes the estimator and remains separate. Agent review does
not supply human scientific release confirmation.
