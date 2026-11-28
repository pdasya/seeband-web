# Constant acoustic prefactor in p-type PbSe

This review experiment tests one Kane light-hole band at L and one parabolic heavy-hole band at Σ. It runs independently of the production fitter. Chasapis et al. measured three sodium fractions at different fixed hole densities. The three values of the constant ratio are profiled independently. No parameter is shared across specimens.

## Two forward calculations

- **Moving bands** use the separate direct L gap, L–Σ valence offset and L DOS mass in Table I as functions of temperature, with the published L ellipsoid anisotropy. Both bands share the chemical potential obtained from the reported total hole density. Extending the tabulated laws below 300 K is an assumption. The published temperature-dependent transport fit covers the high-temperature range.
- **Fixed bands** use the same carrier balance, holding all band parameters at their 300 K values and using the isotropic Hall convention of the TDD. This tests the fixed-parameter model at a specified material input. It is not an optimization over unknown edges, nonparabolicity or masses.

Both use the Table I total Σ DOS mass of 2.5 free-electron masses. The authors report that the most heavily doped sample required a varying heavy mass to describe the Hall maximum. Its temperature dependence is insufficiently specified here for an exact replay. The highest-doping comparison is conditional on the listed constant mass. Counts of equivalent valleys are already included in the DOS masses. Conductivity amplitudes absorb the remaining channel scale. [Paper, Table I](https://arxiv.org/pdf/1502.01087#page=40) · [Carrier balance and experimental hole densities](https://arxiv.org/pdf/1502.01087#page=21) · [Heavy-hole mass discussion](https://arxiv.org/pdf/1502.01087#page=25).

## Constant and published weights

With L as band 1 and Σ as band 2 the TDD defines $w_2=\sigma_{0,\Sigma}/\sigma_{0,L}$ and $\sigma_\Sigma/\sigma_L=w_2 F_0(\eta_\Sigma)/J_{0,L}$. The paper uses generalized acoustic integrals for both bands, with $J_{0,\Sigma}=F_0(\eta_\Sigma)/3$. Its Eq. 14 gives $\sigma_L/\sigma_\Sigma=f_0 J_{0,L}/J_{0,\Sigma}$, hence $w_2=1/(3f_0)$. Both sides describe the same changing fractions of the total conductivity. Neither is the room-temperature mobility ratio. The partial Seebeck coefficients use the first powers of these fractions and the partial weak-field Hall coefficients use their squares. [Paper, Eqs. 12–17](https://arxiv.org/pdf/1502.01087#page=12).

The comparison labelled **published** uses approximate symbol centres from Figure 7(d), linearly interpolated in $f_0$ between 300 and 900 K. The 50 K grid, including its two endpoints, is read from the x-axis. The y-axis major interval is one unit. At a rendered page height of 2200 px, one unit spans approximately 89 px and overlapping marker centres are readable to roughly ±0.07 in $f_0$. These digitized values are inferred parameters from the authors' fit to the same specimens. This is a comparison of descriptions on shared data. No low-temperature extrapolation enters its scores. [Tabulated readout](published_f0.csv) · [Figure 7(d)](https://arxiv.org/pdf/1502.01087#page=39).

## Objective and replay

For each specimen and structure, minimize the sum over observables of the mean squared residual divided by the mean squared measured signal of that observable. Each curve therefore contributes once regardless of its units or point count. These are descriptive scales. No experimental standard deviations enter the objective. The script also profiles each observable separately using the same fixed structure. No bound on a material amplitude is chosen: the search brackets the measured conductance crossovers in $\log(w_2)$ with 40 additional natural-log units on each side, checks both exact single-channel limits and refines the sampled interior minima at two grid spacings. A 30 K near-dark-band regression recovers equal conductances when the underlying shapes differ by eleven orders of magnitude. Residuals are prediction minus digitized measurement. All peaks reported in the transcript are maxima on the observed temperature grid.

For an automated replay from a PR checkout, run the command below from the repository root. The same test runs in GitHub’s Python core job. It checks the forward limits and all 224 rows (112 measurements in two structural scenarios), including point identities, the presence of the published comparison and predictions. The replay tolerance for calculated values is $5\times10^{-6}$ times the measured signal at each point. This tolerance only covers numerical reproduction.

```sh
uv run --frozen pytest -q packages/seeband_core/tests/test_band_design_evidence.py -k chasapis
```

To regenerate the underlying outputs, run the following commands from the repository root. The first checks normalization and limits. The second regenerates the numerical transcript and the pointwise curves locally. Rendering the figure is optional. The saved PNG used Matplotlib 3.10.0 and the Agg backend. The last command installs that plotting version in an isolated environment.

```sh
cd docs/superpowers/specs/band-composition-v0.7/evidence/chasapis
uv run --frozen python forward_model.py
uv run --frozen python compare.py --curves curves.csv
MPLBACKEND=Agg uv run --isolated --no-project --python 3.12 --with matplotlib==3.10.0 python plot_curves.py
```

[Marker calibration and reading uncertainties](MEASURED_DIGITIZATION.md) · [Forward equations and checks](FORWARD_MODEL.md) · [Measured Seebeck](measured_seebeck.csv) · [Measured Hall](measured_hall.csv) · [Saved numerical results](results.txt) · [Observed and calculated curves](curves.csv)
