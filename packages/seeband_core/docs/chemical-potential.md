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
s = sign(r), where the low-level mass coordinate is r = R/N and the public
`m_eff` is R = m₂/|m₁|. Here N = N₂/N₁ > 0. The signed density mass is
r N^(5/3) = R N^(2/3), giving population weight N |R|^(3/2). The equation is

```text
-p(μ, T) + s n₂(μ - E_g, T) = -p(E_F, 0) + s n₂(E_F - E_g, 0).
```

For r > 0 the exact parabolic-band balance has a unique physical root,
including when the target is zero. For r < 0 both bands are valence;
a finite root exists only when E_F < max(0, E_g). Invalid domains are
rejected. The former statement that DPB at E_F = 0 had no root was wrong:
for r = 1.01, E_g = 1000 K and N = 1, the checked solution at 50 K is
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
`normalized_residual` and per-temperature success `status`. Returned statuses
are always `converged`: failure diagnostics are carried by an exception, not
by a partial result array. An invalid point aborts with an error carrying `temperature`,
`reason` and, when available, `normalized_residual`; no partial array is
used for transport. The existing `*_chemPot_vs_temp` methods return only
the checked roots.

No-root domains use `NoFiniteChemicalPotentialError`, a subclass of
`ChemicalPotentialError`. A fit requires a valid initial evaluation. During
optimization only analytically invalid trial points are rejected; numerical
failures at admissible parameters remain fatal. The bounded two-point numerical
Jacobian reverses or shortens a stencil crossing a no-root boundary. Held
parameters use the same domain rules, including a fully held start. A valid
start extremely close to both a box bound and the coupled density-domain
boundary may be moved outside the domain by SciPy's initial inward adjustment.
That numerical initialization failure is reported explicitly; the wrapper
does not change coordinates, solver or bounds to force an interior point.

Invalid starts and numerical failures become fit status `failed` with the
fixed safe message. A calculation with an uncertifiable density root fails
the whole request with HTTP 422; there are no partial density-root arrays.
This is an intentional contract change from legacy 200/null responses.
Numeric values from exceptions are not copied into fit messages or logs.

## Limits and evidence

The 1e-12 check certifies the implemented density approximation, not the
physical accuracy of Fermi integrals. The negative F₁/₂ tail is evaluated as
A exp(x)/(1 + 0.27 exp(x)), A = 0.886226925452758, algebraically identical to
the inherited approximation. This avoids artificial overflow of exp(−x)
without changing the physical model. For T = 2 K, E_g = 2833.6537 K,
r = 0.25845, E_F = 2192.647 K and N = 7.6606, the checked root is
μ ≈ 1413.766203766843 K, consistent with an independent Boltzmann limit.

The table and positive-tail approximation remain unchanged. Small downward
jumps near reduced energies −9.9 and 19.9 mean the approximation need not be
monotonic or have a unique root even when the exact equation does. A failed
residual check alone does not identify a seam, and no universal floating-point
accuracy floor or seam-induced failure is asserted. The conservation tolerance
is not relaxed.

Density underflow that prevents certification fails the whole request. This
is distinct from subsequent transport cancellation/underflow: the unchanged
F₀ = log(1 + exp(x)) can still round to zero after a successful density solve,
so transport can return nonfinite points (#105). P8 does not claim to repair
all Fermi-integral or transport issues.

Previously observed new fit failures on the P8 solver-only version were optimizer
trial-domain exits after admissible starts, not proof that the data or model
had no solution. The domain-aware fit wrapper now distinguishes those trial
points from numerical failures. The updated fixture below records the actual
post-correction statuses: 354 curves, 33 converged fits and three failures
from the original invalid-bounds inputs. It must not be used as independent validation of
model applicability, identifiability or fit quality. Restoring the default
SciPy residual arithmetic and Jacobian storage layout changes some recorded
parameters and iteration counts on the already flagged collapsed-mass SiP
fits (#107). Their sensitivity to rounding remains a model/identifiability
limitation, not evidence of an improved fit.

Original desktop captures remain unchanged. `tests/fixtures/physics/p8.json`
records the new results and explicit failures for every historical call,
with hashes of the desktop sources. These are implementation-generated
regression expectations, not independent physics validation. Independent desktop compatibility checks, analytic limits, boundary,
conservation and temperature-order tests check separate aspects of the contract. Regenerate from the repository root:

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
