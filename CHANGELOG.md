# Changelog

## Unreleased

- P39 (#292): show the absolute model Lorenz number on a 10⁻⁸ W·Ω/K² scale and
  export the total and per-band values directly in W·Ω/K². SPB and DPB now
  return L directly from the model moments.

- Symmetric compensated DPB models give exact zero Seebeck and Hall
  coefficients when both bands also have equal transport weights. The core
  uses the exact midpoint for the chemical potential, removing roundoff
  that appeared as spikes on the Fit plots.

- P29 (#259): the Fit page previews the selected model curves before data are
  loaded. Adding or removing measurements updates their points and RMSE.

- P27 (#257): Fit and Results show the finite points from a partial calculation.
  Curve gaps and unavailable RMSE values identify the affected quantity,
  temperatures and reason.

- Core 0.4.2 restores combined acoustic-phonon and alloy-disorder scattering for parabolic bands (#249). S-only uses the desktop structural Seebeck curve. Fits with resistivity use the mixed lifetime for each band. [Model and independent evidence](docs/physics/acphdis.md).

- Core 0.4.1 (#247): explicit DPB ionized fits accept a researcher-held relative B in S-only and permit fitting B across the conditional Coulomb benchmark in modes with resistivity.

- U8 (#277): every page of the site and the app has the same favicon, as
  SVG, ICO and an Apple touch icon, drawn from the header's logo by
  `pnpm --filter @seeband/site icons`. The logo and the name in the header
  are one link to the overview, named "SeeBand, overview" for screen readers.

- I4 (#69): UptimeRobot watches `/api/ready` and the site every 5 minutes
  and e-mails the owner on an outage and on recovery; a test outage reached
  the owner. A log sample on the host showed no measurement data, client
  address or user agent. `deploy/README.md` has a runbook for alerts, failed
  deploys, rollback, updates, a full disk and restore.

- I3 (#55): the prototype runs at `https://seeband.duckdns.org` on an Oracle
  Cloud Always Free machine (arm64, 2 OCPUs, 12 GB) at no cost, in place of
  the Hetzner CX23 while F6 is open. It stays out of search engines, takes
  daily security updates with a reboot at 04:00 UTC when needed, refuses SSH
  passwords and root, and backs up its disk weekly. `deploy/host-setup.sh`
  sets up the updates and SSH, and saves the firewall without Docker's
  chains. The steps are in `deploy/README.md`.

- I2 (#54): each merge to main builds the images, pushes them to GHCR as
  `sha-<commit>` and, once a host is configured, deploys them over SSH.
  `deploy/deploy.sh` checks that the public health route answers with the
  new commit and otherwise starts the previous tag again, with the previous
  Compose file. It keeps the images of those two tags and removes the rest. A
  run of the Deploy workflow with a tag rolls back by hand. Only main deploys.
  Deploy secrets live only in the repository's `production` environment,
  limited to main. The first host is a temporary Oracle Cloud Always Free
  machine (arm64), so the images are built for amd64 and arm64.

- P17 (#108), core `0.3.3`: draw local parabolic bands, E = ħ²k²/(2m),
  with k in nm⁻¹, signed single-valley masses and a flat Fermi level, in
  place of the desktop's sketch, and drop the `band_diagram_formula` flag.
  The band diagram API returns `wavevector_nm_inv`, and
  `reference_mass_assumed` for every mode without Hall data, SPB or DPB,
  where the curvature takes a band-1 mass of mₑ because no data set its
  size.

- P16 (#107), core `0.3.2`. Verified Fit: when only the DPB gap is free in
  the Seebeck stage, from its upper bound, with the Fermi energy held at or
  below that bound, it first searches the bounded gap interval with the true
  objective. Fits that stopped at the bound or in the onset layer below it
  now reach a lower minimum: on the demo with E_F held at 799.9 K, 61.12
  instead of 63.14 µV/K. A fit with E_F held exactly at the bound, which
  failed derivative validation, now converges. The derivative there comes
  from the zero-target plateau and equals the true one-sided limit. A gap
  with no finite lower bound is refused. The search is finite and certifies
  no global optimum.

- I1 (#53): run everything with one command, `docker compose -f
deploy/compose.yaml up --build`. The API image installs exactly `uv.lock`
  and runs as a user on a read-only file system; Caddy serves the site at
  `/`, the app at `/fit` and `/results`, and proxies `/api` with the fit
  stream unbuffered. New `GET /api/ready` answers once the calculation
  workers have started; the API's health check uses it. CI builds and
  starts the stack and checks it through Caddy.

- Core `0.4.0` adds explicit VB+VB, VB+CB and CB+CB double parabolic bands
  with carrier excess derived from a supplied or fitted Fermi energy. Band masses,
  valley counts and the trial energy determine the conserved electron excess.
  Model has no carrier polarity or density fields. Converting a signed-mass
  session carries its saved Fermi energy into Parameters. Already-saved
  fixed-density sessions replay with their archived carrier balance. Historical
  signed-mass requests retain their versioned behavior. See [P18](docs/superpowers/specs/2026-11-20-p18-explicit-dpb-bands-design.md).

- P18: correct the band-edge quadrature for the acoustic and alloy-disorder
  Hall moments in explicit DPB curves. The previous rule biased the magnitude
  of the CB+CB disorder Hall coefficient by 1.17 parts per million at 800 K
  in the reference case.

- Results ZIP exports calculate one curve at a time and retry temporary
  capacity errors. This lets an archive finish while the Results page is
  still calculating its plots.

- P28 (#258): loading Seebeck data preserves manual starting values. Both
  automatic and requested estimates respect held and fixed parameters in
  each fit mode. Use **Initial guess** to replace eligible manual starts.

- P14 (#105), core `0.3.1`. Stable Fermi integrals extend SPB Hall above the
  former reduced-potential cutoff. Dilute bands give corrected Seebeck
  contributions and finite Seebeck, Lorenz and electronic thermal values
  where intermediate operations previously failed. Intrinsic DPB density
  balance remains certifiable at lower temperatures and preserves exact
  compensation for symmetric bands.
- P14 changes some fitted endpoints. Verified Fit uses the same sequential
  objectives with a stable profiled resistivity derivative. The recorded D1
  fit now reaches conditional stationarity with a large Hall residual. The
  recorded Si:P fits give smaller Seebeck errors and larger resistivity
  errors with a collapsed mass ratio. The existing legacy D1 collapse
  warning still applies after its endpoint moves. Compare runs using both
  the method and the reported core version.
  See [validation and regression notes](packages/seeband_core/docs/golden-results.md#stable-fermi-integrals-p14).

- FS12 (#56), tooling only: with `?timing` in its address, the fit screen
  records User Timing entries for how long live curves take, from a change
  to its answer and to each chart's painted frame, and
  `apps/web/scripts/replay-calc.mjs` and `measure-latency.mjs` measure them
  against a deployed app and API. No measurement or decision yet; results
  are unchanged.

- S6 (#68): add the site's search-engine base. A build with
  `SEEBAND_SITE_URL` gets canonical links, `og:url`, a sitemap and a
  `robots.txt` that keeps search engines out of `/fit`, `/results` and
  `/api/`; a build without it, for the prototype host, keeps every page out
  with `noindex` and `Disallow: /`. Every page has Open Graph tags, and the
  overview a schema.org `SoftwareApplication` description.

- S5 (#67): add worked examples at /examples/ on the three example sets of
  the desktop SeeBand, with screenshots and numbers from runs of this
  version: choosing the scattering mechanism for Fe2VAl0.9Si0.1, a gap
  outside the default bounds for Si:P, and AWI32, which no single mechanism
  describes. Each page states its limits and how to reproduce it.

- S4 (#66): add the user guide at /guide/, adapted from the desktop SeeBand's
  PDF guide (MIT) to the web app, on the Fe2VAl0.9Si0.1 example, with
  screenshots and numbers from runs of this version. It corrects the desktop
  guide's 641 K = 0.059 eV to 0.055 eV, uses κ_e throughout instead of also
  λ_e, and gives its references in full where they could be identified.

- Verified Fit: use an equivalent in-bounds plateau reference when both
  DPB energies are free and meet at the upper gap bound. Check that the
  residuals match before using the reference for the derivative or as a
  starting point. Keep the original endpoint on ties.

- Verified Fit: check the free DPB gap derivative on the intrinsic side of
  the conduction edge when that stencil fits the bounds. For joint fits
  of the gap and Fermi energy, try a bounded restart across the gap from a
  near-edge endpoint. Reject failed exploratory trials and certify the
  retained solution through the final conditional audit.

- DPB Hall fits and curves include the absolute valley multiplicity of
  band 1. The fitted `m1` is a mass per valley. Absolute carrier densities
  in the Hall mode use the same multiplicities. A mass from the previous
  Hall normalization maps to the new convention by dividing it by
  `N1^(2/3)` at the same band shapes.

- Verified Fit: search both permitted sides when a free DPB Fermi energy
  remains in a positive gap after a stage solve. Probe toward each edge,
  polish candidates with lower stage cost, and repeat the search in the
  final conditional audit. Fits constrained to the gap still report the
  Fermi energy as undetermined.

- P16 (#107): flag a DPB Fermi energy in a positive valence–conduction gap,
  including either edge, where transport cannot locate E_F within the gap.
  The warning changes no calculated values or fit behavior.

- P15 (#106): distinguish zero mass and the SPB and DPB Fermi-energy
  constraints in curve failures. The API returns HTTP 422 with a
  reason-specific detail. Fit failures distinguish the finite-root domain
  from numerical certification failures.

- R11 (#187): add the Lorenz number L(T) = kappa_e/(sigma*T) as a derived curve
  in modes with rho, in W*Ohm/K^2 and in units of L0 = pi^2/3 (k_B/e)^2, with
  export. For DPB, show the effective L with its bipolar part, and each band's
  own L. It is made from the existing kappa_e and sigma, so no other number
  changes; their known issues carry over.

- Core `0.3.0`: replace public acPhDis with ionized impurity scattering for
  SPB and DPB, including S-only. Use the approved tau(E) proportional to E^(3/2)
  approximation with lambda=2, consistent longitudinal, Hall and electronic
  thermal moments, and explicit immutable scattering exponents. Retain acPh/dis
  behavior and historical mixed-scattering captures. Ionized fits require
  Verified; SPB estimates follow scattering and DPB neural estimates are
  unavailable for this mechanism. See [the model contract](packages/seeband_core/docs/ionized-impurities.md).

- Reuse certified chemical potentials for exact repeated physical inputs within
  a verified fit. Preserve prediction budgets and fresh terminal audits. Avoid
  duplicate demo/API fits in tests while retaining their assertions; run golden,
  core and API CI test groups independently behind the required Python gate.

- Allow 180 seconds by default for API fits, configurable as before, after
  verified demo fitting exceeded 60 seconds on hosted Linux. Concurrency and
  input limits remain in force; numerical certification criteria are unchanged.

- P19/P6 (#176, #85), core `0.2.0`: default to `verified-sequential-v2`;
  preserve `legacy-sequential-v1` by explicit selection. Profile free inverse
  amplitudes, scale and validate remaining stage derivatives, and check
  conditional optimality at the same final vector. Verified DPB fitting uses
  public R coordinates and converts R/N once at evaluation. Preserve staged
  absolute objectives, physical kernels, input data, user bounds and held values.
  Add algorithm provenance and numerical/consistency/residual/identifiability
  diagnostics across API, session and exports. Numerical settlement does not
  establish physical adequacy or uncertainty. Built-in preview RMSE evaluates
  directly at measured temperatures; pointwise percentages are unavailable at
  measured rho/Hall zeros. See [verified sequential fitting](packages/seeband_core/docs/verified-sequential-fit.md).

- P13 (#104), core `0.1.4`: use positive mass-magnitude weights for
  longitudinal DPB transport in S-only, single-scattering and mixed-scattering
  modes, including band contributions. Keep signed mass coordinates, carrier
  density and Hall carrier signs; Hall uses the corrected resistivity. DPB fits
  retain the signed-start branch, exclude zero without adding a mass floor, and
  intersect bounds with that branch. Density solving, fit objectives and
  tolerances are unchanged. Remove `negative_m_eff_weight`; P6 iterative
  nonunit-degeneracy bounds, P16/P19, and numerical underflow remain open.
  P18 explicit band types and CB+CB are deferred. Focused physical-limit tests and synthetic fit recoveries cover both mass
  signs. These checks are not measurements or validation of neural guesses. Human physicist
  confirmation and desktop parity remain separate release gates. See
  [positive DPB weights](packages/seeband_core/docs/dpb-positive-weights.md).

- P11 (#102), core `0.1.3`: retain the temperature-dependent acPhDis band
  weight in total DPB Seebeck, consistently with the weighted band contributions.
  Fits, curves and RMSE use the corrected pointwise expression. C/D conversion,
  least-squares residual scales, bounds and stopping thresholds are unchanged.
  Remove only `acphdis_band_weight`; preserve desktop/P8 evidence and record
  affected results separately. Restore the independent example-03 outer-loop
  check. Human scientific acceptance and desktop parity remain separate.

- P9 (#88), core `0.1.2`: choose the DPB neural network from the actual minimum and
  maximum temperatures, then sort paired temperature/Seebeck rows before
  preparing its input. Reversed or shuffled distinct-temperature rows now use
  the same network and prediction as sorted data. Keep the unsorted-input provenance warning,
  with corrected wording. Legacy no-net first/last fields now report actual
  minimum/maximum coverage. Network weights, range priority, polynomial
  degree and fit criteria are unchanged. Preserve original desktop captures
  and record the corrected reversed-row expectation separately.

- P8 (#87), core `0.1.1`: solve the signed carrier balance independently at
  each temperature with a checked bracketed method. Use the same negative-tail
  Fermi approximation in a stable algebraic form. Reject analytically invalid
  optimizer trial points without hiding numerical failures at valid parameters;
  invalid starts and uncertifiable density roots still fail explicitly. Keep
  desktop compatibility tests alongside separate P8 regression expectations.
  No bounds, fit weights or conservation tolerance are relaxed.

- Documentation review: correct the signed SPB Hall cutoff and clarify DPB
  convergence timing, interpolation coverage, degeneracy cancellation and the
  open negative-weight interpretation. No calculation behavior changed.

- P10: expose the installed `seeband_core` version (`0.1.0`) in health,
  calculation and fit API responses, and record separate server, fit and curve
  provenance in shared export headers. This is result metadata only; it changes
  no formulas or fit behavior. Older results without a recorded version remain
  unknown and are not assigned a version retroactively. This is not release
  approval; scientific confirmation and the desktop parity work remain open.

- FS18: preserve a conductivity file's source quantity when requesting
  interpolation without an explicit column mapping. Explicit mappings and
  chosen units remain in use. Browser regressions cover conductivity upload,
  headerless column choice, S/cm units and the resistivity sent to a fit.

- P7 (#86): evaluate interpolation only on the overlap of each quantity's
  measured temperature range and the requested fit range. Unsupported or
  too-short overlaps fail explicitly instead of extrapolating synthetic
  points into the fit. Show when measured coverage limits the range; retain
  legacy extrapolation provenance warnings. The polynomial degree and fit
  criteria are unchanged, with separate corrected regression expectations.
  An overlap the data narrow needs 40 K, so that the grid has two points;
  each refusal says why (`interpolation_failure_reasons`); a window with no
  measured point says that the polynomial alone sets it; and results and
  exports name the range a fit used.

- P6 (#85, S-only scope): use the same degeneracy-weighted mass in DPB S
  fitting and drawing. Public mass coordinates, bounds and uncertainties
  stay unchanged; the low-level model receives R/N on both paths. Add
  nonunit-degeneracy synthetic regression results and remove only the
  S-only mismatch warning. The iterative-mode mass/bounds warning remains.

- P5 (#84): require both parameter groups to converge in DPB acPhDis fits.
  Zero-valued parameters no longer cause division by zero, and nonfinite
  changes cannot be reported as converged. Unchanged zeros have zero change;
  leaving zero requires another iteration. Preserve historical desktop
  captures and record corrected fit expectations separately. The independent
  acPhDis Seebeck grid-dependence issue (#102) remains flagged. A parameter
  that is not finite now fails the fit at once. NUM-2 of #84 is not fixed: a
  fit from E_F = 0 still converges at its start values (#106, #176).

- P4/P12 (#83, #103): enable SPB S + ρ + R_H after correcting signed
  mass initialization, bounds and recovery, the mass control scale, and the
  mixed-scattering C return scale at 300 K. SPB Hall curves and fits now use
  the chemical potential at each temperature, conserving carrier density.
  Hall factors recover the degenerate limit 1 and nondegenerate limit 3π/8.
  Synthetic regression results replace no historical desktop captures.
  Every fit now sorts its points by temperature, so an API client's order
  gives the result a sorted file does; a Hall point with signed reduced
  potential x = sign(m) μ(T)/T above 700 is NaN rather than a failed curve;
  a start mass of 0, on an empty branch, or of the wrong sign for R_H fails with
  its reason. The band-mass error is conditional on E_F.
  Human physicist confirmation and parity/author review remain pending;
  enabling this mode is not scientific release approval.

- P3 (#82): convert acPhDis C and D from dimensionless ratios at 300 K
  to temperature scales in SPB/DPB conductivity, thermal conductivity and
  per-band curves, consistently with resistivity. Corrected σρ equals 1.
  Remove the obsolete scale warning and add corrected golden expectations.
  The separate grid-dependent total-Seebeck error (#102) remains flagged.

- P2 (#81): correct the DPB Hall prefactor for acPh, dis and acPhDis.
  R_H doubles at fixed parameters. At fixed measured R_H, unconstrained m₁
  increases by 2^(2/3) and inferred carrier density doubles. Regenerate the
  synthetic demo and remove the `dpb_hall_prefactor` warning. Original desktop
  captures are preserved, with separate P2 regression expectations.

- Initial guess now targets the selected SPB or DPB model. SPB estimates its
  Fermi energy numerically from S(T), preserves absolute mass magnitude, and
  chooses the carrier sign. Previously, automatic loading always guessed DPB
  and the SPB button was unavailable. DPB network weights and predictions are
  unchanged. The API adds `numerical_guess` as an initial-guess response.
