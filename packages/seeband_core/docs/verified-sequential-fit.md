# Verified sequential fitting (P19/P6)

Core `0.2.0` defaults to `verified-sequential-v2`. Requests may explicitly select
`legacy-sequential-v1` to reproduce the core 0.1.4 fitting path. A failed or
stalled verified fit never silently falls back to legacy. The result records
the algorithm that actually ran; historical results without this information
remain unknown.

## Preserved scientific contract

The verified route shares the P13 physical kernels and the P8 density solver.
Carrier branches, input values and held parameters are retained. Each stage
still minimizes its unweighted absolute squared residuals, using the existing
scales S × 10⁶, rho × 10⁸ and Hall × 10¹⁰. There is no joint objective, pointwise
relative weighting, logarithmic data transform, robust loss or mass penalty.
The joint estimator and uncertainty choices remain P22/P23.

All verified optimizer coordinates and bounds use public R = m₂/|m₁|. Kernels
receive r = R/N exactly once. This completes the iterative P6 coordinate
correction for the verified route. Explicit legacy reproduction retains its
documented nonunit-degeneracy limitation and warning.

## Numerical stages

For fixed shape parameters, resistivity is rhoᵢ = hᵢ/A. With u = 1/A, its
conditional least-squares solution is

```text
u* = clip((h · y) / (h · h), inverse_amplitude_bounds).
```

The inverse bounds are derived from the original amplitude bounds. This solves
the same resistivity objective; it does not fit conductivity instead. Free
Hall amplitudes have an analogous conditional solution. Held amplitudes keep
their supplied values. A zero-information shape does not determine an amplitude;
a singular or unattained endpoint is reported explicitly rather than replaced
with an arbitrary positive floor.

Free nonzero masses use signed-branch log-magnitude coordinates, preserving the
public bounds; zero-permitted scattering variables remain linear and scaled.
Derivatives use admissible fourth-order stencils checked independently at half
the step, searching both smaller and larger steps to balance truncation and
evaluation noise. Invalid density trials can be rejected; numerical failures
at admissible parameters remain errors. Final checks use the returned vector,
including its exact amplitudes, rather than the previous stage's parameters.
Conditional objective reductions and independent projected-gradient checks
must support convergence. A rho update that changes the Seebeck weight therefore
requires another consistent sweep.

Recovery starts are bounded and deterministic. The selected carrier branch and
held values remain fixed. Evaluation and sweep budgets are finite; cycles,
stalls and budget exhaustion are distinct diagnostic reasons. Neither solver
success nor a small change from the starting vector is enough by itself.

One DPB recovery failure was reproduced with the bundled synthetic demo Seebeck
data, acoustic phonons, held `m_eff = 1.2` and `band_gap = 800 K`, and a free
`fermi_energy` starting at `400 K` with default bounds. The doubled seed lands
at `800 K`, exactly the conduction-band edge. At that point the derivative
estimates from scaled steps `1e-5` and `5e-6` differed by about 41% relative to
the smaller-step estimate. The old fit reported `derivative_validation_failure`.
The Fermi-energy derivative is exactly zero on the closed positive gap
interval. When a stage solve leaves a free Fermi energy on that plateau,
the recovery starts from the parameters returned by the solver, including any
updated mass ratio and gap. On each permitted populated side it evaluates up
to 32 offsets, halved toward the edge, using the existing stage objective.
It polishes the best improving probe on each side and retains the lowest-cost
feasible candidate. The final conditional audit repeats the same search.
The finite set of probes and shared evaluation budget define the search coverage.

An optional restart can encounter an inadmissible carrier root or a
derivative that fails validation. Verified Fit discards the failed restart
and keeps evaluating other candidates. An improving probe needs a
validated derivative before retention. If failure in a restart leaves a
material improvement unverified, Verified Fit reports `stalled` and
checks the retained endpoint's predictions and derivatives before
returning it.

On the same demo, a plateau RMSE of
63.136 µV/K falls to 0.8084 µV/K at `fermi_energy ≈ −150.1195 K`, with the
same fit objective, held values and certification thresholds. When the bounds
keep the fit in the gap, the warning still applies: transport does not locate
the Fermi energy there (#107).

With a free gap, a stencil that narrows the gap across the conduction edge
also samples the onset of carriers. Verified Fit keeps the gap stencil on
the intrinsic side when the bounds allow it and still checks refinement at
half the step. This changes the derivative probes while using the original
fit bounds. If Fermi energy remains on the plateau after fitting the gap,
the recovery described above uses the updated stage parameters. Before
polishing another populated-side seed, it checks that the seed's evaluated
cost still improves on the best candidate found so far. When no intrinsic-side
stencil is available, the ordinary admissible derivative check still applies.

When the gap and Fermi energy are both free and the stage ends just outside
a positive DPB gap, it can also restart on the opposite populated side.
The numerical distance threshold is one nominal finite-difference step.
The restart respects the Fermi-energy bounds and preserves the other
coordinates at its starting point. The conditional audit checks the same
recovery at the final parameters.

Starting the synthetic demo at `band_gap = fermi_energy = 800 K` with every fitted
parameter free gives a Seebeck RMSE of about `0.807 µV/K` in both the
Seebeck-only and sequential Seebeck, resistivity and Hall modes. Both fits
converge at `fermi_energy ≈ −150.17 K` within the fit bounds.

On the same demo, with only `m_eff` held and both energies starting at
`800 K`, the fit now settles at `band_gap ≈ 799.8726 K` and
`fermi_energy ≈ −150.1328 K` with a `0.808359 µV/K` RMSE. A noiseless
conduction-side test from the same start recovers a `650 K` gap and
`1000 K` Fermi energy. A separate intrinsic test recovers a `900 K` gap
while leaving the Fermi energy undetermined. On the demo, setting the gap
upper bound to the initial edge at `800 K` still gives an explicit derivative
validation failure: no widened-gap probe is admissible.

Synthetic DPB Seebeck curves generated with the same mass ratio and gap,
31 temperatures from 50 to 800 K, and Fermi energies 0.05 K or 0.0001 K
outside either edge serve as near-edge regressions. The fits recover those
energies from a 400 K start, including when the generating energy is at the
only accessible outer bound. With all parameters free on the bundled demo,
the start (m₂/m₁ = 1.2, E_g = 800 K, E_F = 0 K) now gives about
0.807 µV/K RMSE. The earlier plateau result gave 48.34 µV/K.

## Result interpretation

Algorithm and diagnostics travel with the API result and exports. Diagnostics
separate numerical termination, conditional-stage consistency, objective values,
evaluation/recovery counts, input-grid residuals and detected unidentified
parameters. Input-grid residuals refer to the data submitted for fitting; with
interpolation enabled these may be interpolated points rather than independent
raw measurements.

Residuals use the same final parameters at each quantity's own input temperatures.
They include absolute RMSE in core units and relative L2 residual when the data
norm is nonzero. A zero signal has no relative L2 value. Numerical convergence
does not establish physical adequacy. Residual adequacy and uncertainty are
`not_assessed`; the verified route supplies no manufactured zero error bars.
Detected structural nonidentifiability is reported, while an empty list is not
a proof of full identifiability. Complete rank/profile inference remains P23.

`stalled` retains a usable endpoint and diagnostics but is not convergence.
`iteration_limit` reports budget exhaustion. Invalid starts and numerical
failures return `failed`. The UI distinguishes numerical settlement from a
successful physical parameter determination.

The existing preview RMSE now evaluates built-in SPB/DPB kernels directly at submitted
measurement temperatures instead of interpolating a plot grid. Its historical
pointwise percentage metric remains separate from fit diagnostics' relative L2.
If a rho/Hall measurement is zero, the core helper returns an unavailable
percentage; absolute fit diagnostics remain meaningful. The existing `/api/calc`
contract rejects submitted zero rho/Hall values, and the web preview excludes
them. Custom registered models without this kernel
evaluator retain their grid-based metric fallback. Full residual UI work remains P21.

## Independent reproductions and validation

Before implementation, a noiseless fixed-shape synthetic DPB disorder stage
returned solver success with relative rho residual 0.159816714. Exact reciprocal
amplitude profiling reduced the same objective to a residual of 8.14 × 10⁻¹⁷;
an analytic amplitude Jacobian also recovered the known solution. Merely changing
`x_scale` did not repair that reproduction.

An ordinary synthetic acPh DPB cycle stopped after seven sweeps. Its returned
parameters gave Seebeck SSE 1235.87210 (µV/K)², while another conditional S fit
gave 0.61020214. This independently motivates final-vector consistency checks.
These are synthetic demonstrations of numerical defects, not fits to measurements.

With the new method's unchanged finite evaluation budget, this outer reproduction
returns `iteration_limit`, with final Seebeck SSE about 0.2103 and rho SSE about
0.03532. Its remaining S-stage optimality check fails, so it does not claim
convergence. Higher-order derivative checks spend more evaluations per sweep;
the evaluation count includes the terminal diagnostic work after the optimization
budget is exhausted.

Historical SiP and D1 endpoints independently show feasible conditional amplitude
improvements under unchanged bounds. Their original captures remain historical
evidence, not required parameter or physical-quality targets for the new method.
Implementation-generated P19 regression evidence must be kept separate from
desktop/P8/P11/P13 captures. Real-data residuals are reported honestly; the
algorithm contains no sample-name conditions or data-specific fit terms.

The separate [P19 capture](../tests/fixtures/physics/p19.json), reproduced with
`scripts/capture_p19_results.py`, records the following aggregate observations
on the environment named in that file. They are generated observations rather
than portable parameter goldens or physical acceptance targets.

| Recorded input            | Numerical outcome             | Relative L2 S | Relative L2 rho | Interpretation                                                                                              |
| ------------------------- | ----------------------------- | ------------- | --------------- | ----------------------------------------------------------------------------------------------------------- |
| D1 / example 01           | failed: derivative validation | unavailable   | unavailable     | The profiled rho derivative near the G upper bound cannot be certified; this is not a density-root failure. |
| SiP, mixed S + rho        | conditional stages consistent | 61.94%        | 62.46%          | Poor fit remains; intrinsic Fermi energy is explicitly unidentified.                                        |
| Example 03, mixed S + rho | conditional stages consistent | 2.00%         | 17.99%          | Numerical consistency does not establish residual adequacy.                                                 |

D1's separate 1,000-evaluation test reaches a finite endpoint beyond the original
mass-derivative failure. It does not assert default-budget convergence. The
default run still refuses certification when a later derivative fails the
unchanged refinement criterion. No tolerance is relaxed to force that fit.

Focused tests cover the numerical defects and applicable SPB/DPB fit/scattering,
branch, degeneracy, held/free, boundary and zero-information cases. A finite test
matrix does not guarantee a global optimum or unique parameters throughout a
continuous domain. Physical limits, derivative refinement, exact profiling and
legacy reproduction provide independent checks alongside generated regressions.

The owner approved the algorithm and P6 scope before implementation. Independent
agent reviews do not replace human physicist confirmation or the desktop parity
release gate (#71).

The verified demo fit exceeded the previous 60-second API deadline on hosted
Linux. The API now defaults to a configurable 180-second fit deadline, retaining
concurrency and input-size limits. This is an execution budget, not a relaxation
of numerical certification; sufficiently difficult requests can still time out.

## Exact work reuse and test runtime

A fit-local cache reuses successful P8 chemical-potential arrays only for exact
repeated physical inputs. Its key includes model, temperature shape/dtype/order
and values, and the actual mass, gap, Fermi energy and degeneracy arguments,
including their scalar representations. SPB preserves its existing full-mass
versus mass-sign calls. Scattering and transport amplitudes do not change the
density balance. At most 32 arrays of 10,000 points are stored; callers receive
copies, failures are not cached, and larger grids bypass storage.

This cuts inner root work without changing prediction-evaluation counts,
objectives, bounds, derivative checks or iteration budgets. Terminal diagnostics
independently recompute roots without this cache. Optional kernel arguments
default to the original calculation path, preserving legacy calls.

An instrumented fixed-band DPB rho-stage profile kept 106 prediction evaluations while reducing
identical root-array solves from 106 to one: approximately 0.637 to 0.035 seconds
on the recorded local environment. That is a stage-specific result. A complete
SPB fit was almost unchanged (0.930 to 0.910 seconds, identical result); a heavier
DPB core/API test decreased from about 94 to 77 seconds. These timings do not
guarantee the same speedup on every model or machine.

Demo tests share deterministic exact-case fits with deep-copy isolation.
API result and iteration-event assertions inspect one actual core/API pair per
case rather than executing that pair twice. No HTTP response cache bypasses
validation. CI runs golden, remaining core and API tests on independent runners;
the required `Python` gate succeeds only after every test group, static check and
package build succeeds. Verbose test names, slow-test durations and diagnostic
stack dumps expose long-running cases without relaxing their assertions.

## Sources

The exact conditional amplitude solution follows directly from the stated
least-squares problem. SciPy documents the numerical relevance of parameter
scales, derivative approximations, termination reasons and constrained optimality:
[curve_fit](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html)
and [least_squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html).
