# Initial guess

Initial estimates use every uploaded Seebeck row, independently of the fit interval.
The web client targets the selected model and applies matching parameters to its
fit modes. It preserves other transport parameters and ignores stale answers
after data, parameter or scattering changes.

## SPB

The numerical search sorts measured rows and uses up to 24 points. It requires
at least three distinct positive temperatures, a nonzero Seebeck signal, and
no sign reversal. It minimizes squared Seebeck residuals in microvolts/K using
the selected SPB forward model: lambda=0 for acPh/dis and lambda=2 for ionized impurities. The fitted coordinate is log(|E_F|), bounded
between 1 K and the control maximum of 3000 K. The Seebeck sign selects the
carrier branch. The result is rounded to control resolution.

Absolute mass is not identifiable from S(T). The core returns a signed unit
reference mass. The client preserves each mode's existing mass magnitude and
applies the returned carrier sign; a zero mass is replaced by unit mass.

This is a starting estimate without uncertainty or a uniqueness guarantee.
Inspect the calculated curve before running the full fit.

## DPB

Ionized impurity estimates are unavailable: the supplied neural networks were
trained for the previous scattering law. The API returns `unsupported` with
`scattering_not_supported`; the client keeps the current starts and explains
why manual input is needed.

The desktop-compatible neural algorithm and weights are unchanged. It selects
the first covered temperature range, fits a degree-five Chebyshev polynomial,
and feeds seven interpolated values to the corresponding network. Predicted
mass ratio, band separation, and Fermi energy are rounded and clipped to the
controls. The existing warnings for unsorted input, underdetermined polynomial
fits, and a mass ratio rounding to zero remain in place.

Retraining is deferred until data collection is complete; see
[issue #168](https://github.com/pdasya/seeband-web/issues/168).

## Input domain and quality

SPB assumes E_F lies inside the band at T = 0 (#106).
Rows below E_F,max / 700 (about 4.29 K) are omitted with a warning to avoid
existing lambda=0 F0 overflow. The same conservative input cutoff remains
for ionized estimates, whose transport evaluator uses stable moments. At least three usable
distinct temperatures must remain. Unsupported signals return a typed reason:
sign_change, zero_seebeck, or too_few_temperatures.

The response includes RMS error in V/K, a bound warning, and a residual warning
when RMS error exceeds 20% of RMS signal. This is a quality heuristic, not a
physics threshold for single-band validity. The bounded search cannot represent arbitrarily small/large |S|. For the
lambda=0 model near 300 K, this means roughly below 30 or above 900 microvolts/K;
ionized impurity estimates have a different reachable Seebeck interval.

Automatic guesses are tracked per dataset and model. Changing models estimates
its starts once; returning to a previously guessed model keeps edits. The server
marks sign-only parameters; the generic client preserves their magnitude, using
each parameter's core default magnitude for zero. See D28 for automatic SPB sign.
