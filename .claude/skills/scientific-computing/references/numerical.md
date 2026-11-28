# Numerical reliability and SciPy

Choose tolerances from acceptable error in the observable, with explicit parameter/residual scales. Check solver status and the original equation's residual separately. For example, `fsolve`'s `xtol` controls relative changes between consecutive iterates, not an equation-residual threshold. Establish root existence where possible; a sign-changing bracket supports a continuous scalar root only across a domain without poles. A local root does not establish uniqueness or enumerate all roots.

Inspect cancellation, overflow and underflow before changing algorithms. Prefer stable equivalent expressions such as `log1p`, `expm1` or `logaddexp` where appropriate, while preserving domains and branches. Verify such replacements within the assigned behavior scope.

For interpolation, state the input domain and extrapolation policy; check endpoints and knots. Separate interpolation error from measurement error. Preserve monotonicity or positivity when required by the model.

Refine quadrature/grid resolution and solver tolerances independently; test boundary and extreme regimes. When the model predicts pointwise values independent of a sampling grid, compare shared points after adding/reordering neighboring temperatures. Record convergence in the requested observable; a small internal error estimate alone is insufficient.

For a high-precision cross-check, formulate an independent expression in mpmath and construct inputs from exact integers/rationals or decimal strings at the chosen precision. Increasing precision after importing rounded floats cannot recover lost digits. Vary precision and compare with an analytic limit or separate formulation; repeating production logic at higher precision can repeat its error.

Consult installed-version contracts in official [SciPy fsolve](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.fsolve.html), [SciPy integration](https://docs.scipy.org/doc/scipy/reference/integrate.html) and [mpmath precision](https://mpmath.org/doc/current/basics.html) documentation. Report executed convergence checks and unresolved error sources.
