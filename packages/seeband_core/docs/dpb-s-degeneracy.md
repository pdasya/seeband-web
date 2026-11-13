# DPB S-only degeneracy correction (P6)

DPB S-only fitting and drawing use the same low-level mass r = R/N, where
N = N₂/N₁ and the public `m_eff` parameter R is the signed band-2 mass
relative to the magnitude of the reference band-1 mass. See the
[public model conventions](../../../apps/site/conventions.md).

The old fitting objective passed R directly while the drawn curve passed
R/N. For R = 1.2, E_g = 800 K and E_F = −150 K at N = 3, the old paths
differed by 120.317 µV/K over 16 temperatures from 100 to 800 K. This was
reproduced before changing the objective. At N = 1 the paths already agreed.

P6 converts the optimizer's R to r inside the S-only model callback. The
optimizer's starts, bounds, returned parameters and covariance remain in R
coordinates. No transport, carrier-density or chemical-potential formula
changes. In particular, the conversion gives density weight N |R|^(3/2)
and transport weight N/R, consistent with the existing drawing path.

## Validation and limits

Tests compare the exact objective with a redraw at nonunit degeneracy,
recover synthetic model inputs, check fractional and equivalent degeneracy
ratios, and preserve input arrays. Historical desktop captures remain
unchanged; nonunit-N synthetic expectations are recorded separately. They
are generated model data, not measurements or proof of parameter uniqueness.

Matching the objective to the drawn curve removes a consistency error. It
does not guarantee that a fit of measured data has low RMSE or physically
identifiable parameters. Local minima, active bounds, collapsed masses and
the inherited chemical-potential solver remain relevant.

On Python 3.13.18, NumPy 2.5.4 and SciPy 1.18.1, replaying the recorded
S-only inputs, starts and bounds with N changed to 3 gave:

| Example           | Objective RMSE, µV/K | Interpretation                                                   |
| ----------------- | -------------------- | ---------------------------------------------------------------- |
| `01_Fe2VAl09Si01` | 3.263207             | Objective and redraw agree on the same temperatures.             |
| `03_AWI32_SI`     | 3.495436             | Objective and redraw agree on the same temperatures.             |
| `02_SiP`          | 639.6728             | The mass collapses near 6 × 10⁻⁷; the result remains unreliable. |

The SiP measurement grid is nonuniform. A uniform linspace redraw is not
pointwise comparable to its objective: compare the model at the measured
temperatures. The historical approximately 32 µV/K case did not specify
enough inputs to reproduce uniquely; these runs do not claim to explain
every poor fit. Synthetic recovery tests independently exercise a known
model with controlled starts and bounds.

Only the `dpb_s_degeneracy` flag is removed. The iterative-mode output/bounds
inconsistency remains flagged as `dpb_loop_degeneracy`, so #85 is not fully
resolved by this S-only change. Negative-mass transport, band diagrams and
other independently tracked issues are outside scope. Human physicist
confirmation and the #71 parity gate remain pending.
