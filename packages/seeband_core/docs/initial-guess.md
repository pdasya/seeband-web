# Initial guess

Initial estimates use every uploaded Seebeck row, independently of the fit interval.
The web client targets the selected model and applies matching parameters to its
fit modes. It preserves other transport parameters and ignores stale answers
after data or parameter edits.

## SPB

The numerical search sorts measured rows and uses up to 24 points. It requires
at least three distinct positive temperatures, a nonzero Seebeck signal, and
no sign reversal. It minimizes squared Seebeck residuals in microvolts/K using
the existing SPB forward model. The fitted coordinate is log(|E_F|), bounded
between 1 K and the control maximum of 3000 K. The Seebeck sign selects the
carrier branch. The result is rounded to control resolution.

Absolute mass is not identifiable from S(T). The core returns a signed unit
reference mass. The client preserves each mode's existing mass magnitude and
applies the returned carrier sign; a zero mass is replaced by unit mass.

This is a starting estimate without uncertainty or a uniqueness guarantee.
Inspect the calculated curve before running the full fit.

## DPB

The desktop-compatible neural algorithm and weights are unchanged. It selects
the first covered temperature range, fits a degree-five Chebyshev polynomial,
and feeds seven interpolated values to the corresponding network. Predicted
mass ratio, band separation, and Fermi energy are rounded and clipped to the
controls. The existing warnings for unsorted input, underdetermined polynomial
fits, and a mass ratio rounding to zero remain in place.

Retraining is deferred until data collection is complete; see
[issue #168](https://github.com/pdasya/seeband-web/issues/168).
