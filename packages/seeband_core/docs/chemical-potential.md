# Checked chemical potential (P8)

All SPB and DPB chemical-potential, Fermi-integral and transport calculations
use the same signed carrier-balance solver. P8 (#87) replaces unchecked
`fsolve` calls on an absolute residual. A returned value must satisfy the
implemented density equation; an unsuccessful solve raises
`ChemicalPotentialError` rather than supplying a plausible finite number.

## Balance and existence

Energies, including μ, E_F and the band offset E_g, are in kelvin. At each
positive temperature T, solve in η = μ/T. The carrier density at T = 0,
computed from E_F by the existing `spb_carCon`, sets the conserved target.
No doping parameter or band convention is changed.

For SPB the equation is n(μ, m, T) = n(E_F, m, 0). A finite-temperature root
exists only when sign(m) E_F > 0. Mass must be finite and nonzero.

DPB keeps band 1 valence with edge 0, and band 2 with edge E_g and type
s = sign(m_eff). Its density mass remains m_eff N^(5/3), where N is the
positive degeneracy ratio. The equation is

```text
-p(μ, T) + s n₂(μ - E_g, T) = -p(E_F, 0) + s n₂(E_F - E_g, 0).
```

For m_eff > 0 this valence/conduction balance has a unique physical root,
including when the target is zero. For m_eff < 0 both bands are valence;
a finite root exists only when E_F < max(0, E_g). Invalid domains are
rejected. The former statement that DPB at E_F = 0 had no root was wrong:
for m_eff = 1.01, E_g = 1000 K and N = 1, the checked solution at 50 K is
μ = 499.626858019 K with the existing Fermi-integral approximation.

## Numerical checks

The solver uses `scipy.optimize.brentq` on the signed normalized balance,
starting with a symmetric reduced-energy bracket spanning the temperature,
Fermi energy and band-offset scales, and expanding until signs differ.
Each unique temperature is solved independently. Temperatures are sorted
and deduplicated, then roots and diagnostics return in the caller's order.
Changing temperature order or solving a point alone must change μ by no
more than 1e-9 K.

Normalize the signed residual by the larger of the total unsigned
finite-temperature density and the absolute conserved target. The scale
must be finite, positive and at least the smallest normal binary64 value:
subnormal densities cannot certify 1e-12 relative accuracy, and two populations underflowing to zero
cannot certify a zero-target root. Accept a root only with absolute
normalized residual at most 1e-12. Bracketing failure, iteration failure,
nonfinite values or an excessive residual raise an explicit error.

`spb_chemPot_diagnostics` and `dpb_chemPot_diagnostics` return
`ChemicalPotentialResult`: `chemical_potential` in kelvin,
`normalized_residual` and per-temperature `status`. Successful statuses are
`converged`. An invalid point aborts with an error carrying `temperature`,
`reason` and, when available, `normalized_residual`; no partial array is
used for transport. The existing `*_chemPot_vs_temp` methods return only
the checked roots.

Fit wrappers translate this error to status `failed` with a fixed message
that the chemical-potential balance could not be verified. Calculation
workers use the existing calculation-failure response. Numeric values from
an exception are not copied into fit messages or logs.

## Limits and evidence

The 1e-12 check certifies the implemented density approximation, not the
physical accuracy of Fermi integrals. P8 preserves their table and
asymptotic formulas. They have small discontinuities near reduced energies
−9.9 and 19.9; a physical root can therefore still fail the numerical
residual check. Underflow, transport overflow and the separate DPB
weight/degeneracy issues remain. No fit objective, weight, bound or sample
was changed to improve an example's fit. A failed fit is a valid outcome.

Of 390 distinct historical call inputs, this capture records 354 curves,
24 converged fits and 12 failed fits. Ten fits fail the chemical-potential
check (including the 02_SiP starts/optimizer paths and the 01 D1 variant);
two retain the original invalid-bounds failure. Failure is recorded, not
replaced by a visually agreeable fit.

Original desktop captures remain unchanged. `tests/fixtures/physics/p8.json`
records the new results and explicit failures for every historical call,
with hashes of the desktop sources. These are implementation-generated
regression expectations, not independent physics validation. Boundary,
conservation and temperature-order tests check the solver contract
separately. Regenerate from the repository root:

```sh
PYTHONPATH=packages/seeband_core/src uv run python packages/seeband_core/scripts/capture_p8_results.py
```

Human physicist confirmation of the conventions and the #71 desktop/web
comparison remain separate outstanding gates. Agent review supplies neither.

## Timing comparison

On one arm64 Mac with macOS 26.6.2 and Python 3.13.18, the median of five
50-point Seebeck calls from 50 to 800 K changed from 5.45 to 7.00 ms for
SPB (m = 1, E_F = 300 K), and from 10.47 to 13.31 ms for DPB
(m_eff = 1.01, E_g = 1000 K, E_F = −100 K, N = 1). These illustrative
local timings include the new checks; they are not a performance guarantee.
The implementation does not trade conservation checks for a faster fit.
