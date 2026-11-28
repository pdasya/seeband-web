# Fitting and inverse problems

Write the residual vector and objective explicitly, including units, scaling and data/error assumptions. For independent standard deviations, normalized residuals are `(model - data)/sigma`; squared-residual weights are `1/sigma**2`. In `curve_fit`, one-dimensional `sigma` contains standard deviations, while two-dimensional `sigma` is the observation covariance. Correlated errors require the corresponding covariance treatment.

Interpret `absolute_sigma` explicitly: true uses the supplied uncertainty scale; false rescales the parameter covariance by the reduced chi-squared. Returned covariance relies on a local linear approximation and the adopted noise model. Stage-specific covariance from sequential fitting is not automatically the uncertainty of the final coupled fit.

Scale parameters and residuals deliberately. Validate analytic Jacobians against an independent derivative or finite differences with suitable step sizes away from nonsmooth boundaries. Inspect Jacobian rank/conditioning and parameter tradeoffs: a fitted curve can be stable while individual parameters are nonidentifiable. An optimizer success flag does not resolve this.

Use bounded multistart only when justified by the objective landscape; state bounds, seed strategy, reproducible seeds and evaluation/time budgets. Compare distinct solutions and report boundary hits, failed starts and residual structure. A boundary optimum requires constrained interpretation, not an unqualified symmetric interval.

Use profile or bootstrap diagnostics only with a justified error/resampling model, respecting correlations and constraints. Report limitations when data cannot identify parameters instead of manufacturing precision. Consult official [curve_fit](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html) and [least_squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html) documentation for installed-version behavior.
