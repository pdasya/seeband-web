# P18 — Explicit double parabolic bands

For new samples in [#166](https://github.com/pdasya/seeband-web/issues/166),
the researcher selects the band configuration and carrier type (p or n), and
enters or fits the zero-temperature Fermi energy. The signed-density form
below remains the representation for previously saved fixed-density sessions.

## New samples with a Fermi-energy input

Use `explicit_fermi_v1` and `carrier_type` with `fermi_energy` in kelvin,
measured from the edge of band 1. At each trial, compute the signed excess
from both occupied zero-temperature pockets using the masses, multiplicities,
offset and trial energy. Conserve this excess while solving for the chemical
potential at each temperature. Changing a mass, the offset or the Fermi energy
can therefore change the conserved excess between fit trials.

Select **n** for electron excess or **p** for hole excess. For CB+CB at least
one conduction band must be occupied. VB+VB requires at least one hole
pocket. For VB+CB the carrier sign follows the sum of the two populations,
including when the bands overlap. In an intrinsic gap both selections admit
the same compensated solution. The data cannot distinguish different
zero-temperature energies inside that gap. Seebeck polarity alone cannot
determine the sign of the excess when both electrons and holes contribute.

## Saved samples with a signed-density input

| Explicit DPB field                       | Meaning                                                                       |
| ---------------------------------------- | ----------------------------------------------------------------------------- |
| `parameterization = explicit_density_v1` | Discriminator for requests, sessions and exported parameters                  |
| `band_configuration`                     | `vb_vb`, `vb_cb` or `cb_cb`, fixed for the fit                                |
| `band_offset_k`                          | Signed Δ = E₂ − E₁, with E₁ = 0; API energies in kelvin, UI may convert to eV |
| `mass_ratio`                             | M = m₂/m₁ > 0, using positive single-valley DOS masses                        |
| `m1`                                     | Absolute single-valley band-1 DOS mass in electron masses                     |
| `band_1_degeneracy`, `band_2_degeneracy` | Positive valley multiplicities, excluding spin                                |
| `net_electron_density_per_m3`            | D = n − p, in m⁻³, held constant across the temperature sweep                 |

Band labels follow the selected configuration even as Δ crosses zero. In
VB+CB, Δ > 0 is a gap and Δ < 0 is an overlap. Either offset sign is allowed
for equal-type bands. The UI should permit at least ±3 eV as an exploration
range; the researcher sets bounds for a particular sample. Both positive
masses and absolute multiplicities are required in every new mode.

## Carrier conservation

Set sᵢ = +1 for CB and −1 for VB. For T > 0, define ηᵢ = sᵢ(μ − Eᵢ)/T,
with energies in kelvin, and use the **unnormalized** Fermi integral
Fⱼ(η) = ∫₀^∞ xʲ / (1 + exp(x − η)) dx. The positive population in m⁻³ is

```text
Cᵢ = Nᵢ/(2π²) (2 mᵢ mₑ kᴮ T / ℏ²)^(3/2) F₁/₂(ηᵢ).
D  = Σᵢ sᵢ Cᵢ.
```

The prefactor includes two spin states. The signed contribution on a carrier
plot is sᵢCᵢ. Its mobile electric charge density is −e sᵢCᵢ with e > 0.
For any finite T the balance increases strictly with μ because both sign
factors cancel when differentiating each term.

| Configuration | D admitting a finite μ(T)           |
| ------------- | ----------------------------------- |
| CB+CB         | D > 0                               |
| VB+VB         | D < 0                               |
| VB+CB         | Any finite signed D, including zero |

At T = 0 replace the population by
Nᵢ/(3π²) (2 mᵢ mₑ kᴮ / ℏ²)^(3/2) max(sᵢ(μ₀ − Eᵢ), 0)^(3/2).
For a gapped VB+CB pair at D = 0 every μ₀ in [E₁,E₂] satisfies this equation.
Report the interval if a zero-temperature energy is requested. A touching pair
has a single endpoint. An overlapping compensated pair has a unique μ₀.

Use the existing P8 standard for a finite-T solution: absolute balance error
divided by max(C₁+C₂, |D|) ≤ 10⁻¹². Distinguish a wrong-sign input from a
valid input where numerical precision cannot certify a root. In particular,
two underflowed intrinsic populations cannot certify compensation. A repeated
or reordered temperature must give the same solution.

## Transport and symmetry checks

Use the published single-band kernels with each band's own ηᵢ and charge
sign. For the current public scattering laws the longitudinal weight of band
2 relative to band 1, before its band integral, is w = (N₂/N₁)b/M. Use b = 1 for S-only; otherwise use B
for acoustic or ionized scattering and G for alloy disorder. Retain the current
phenomenological ionized relative weight as a documented assumption of this
proposal. A microscopic ionized-amplitude model would require separate
evidence. For positive channel conductivities the weak-field totals are

```text
σ = σ₁ + σ₂                         ρ = 1/σ
S = (σ₁S₁ + σ₂S₂)/σ
R_H = (σ₁²R_H1 + σ₂²R_H2)/σ²
κ_e = T [σ₁L₁ + σ₂L₂ + (σ₁σ₂/σ)(S₁ − S₂)²]
L_total = κ_e/(σT)
```

The interband thermal term also applies to two bands of the same type. The
current positive-weight conventions and their source equations are collected
in [P13](../../../packages/seeband_core/docs/dpb-positive-weights.md).

- **Reflection.** Reverse both sᵢ, μ, Δ and D. Populations, σ, ρ, L and κₑ
  are invariant; S and R_H change sign.
- **Exchange labels.** Reanchor at the old E₂: Δ′ = −Δ, μ′ = μ − Δ,
  m₁′ = M m₁, M′ = 1/M, and exchange N₁,N₂ and the signs. D is invariant.
  For an absolute conductivity amplitude a (A or F), set a′ = a w and
  b′ = 1/b for positive b. Total observables agree and contributions exchange.
  A common shift of both edges and μ alone leaves every ηᵢ unchanged.
- **Identical bands.** Compare two identical copies with one at the same μ
  (twice the SPB D and equal scattering). σ and κₑ double, S is unchanged,
  and R_H halves. At the same total D the chemical potentials generally differ.
- **SPB limit.** Suppress both the second population and its longitudinal
  channel. Setting its scattering weight to zero alone still leaves it in
  the charge balance.

## Legacy parameters and fit behavior

For an old nonzero public signed ratio R, set s₁ = −1, s₂ = sign(R),
M = |R|, and retain Δ and band identity. The legacy kernel consumes
r = R/(N₂/N₁); using |r| as the new single-valley ratio would count the
degeneracy twice. Evaluate the zero-temperature populations above at the
saved E_F with the actual m₁, N₁ and N₂ to obtain D. When using the legacy
`spb_carCon` helper, its output is in cm⁻³ and must be multiplied by 10⁶.
Reject R = 0 with an actionable error.

This maps a fixed parameter set. A held E_F or a rectangular legacy range
in E_F and M does not become the corresponding hold or range in D:
the density also depends on the masses, Δ and multiplicities. Preserve the
historical version, fitted values, original units, holds and bounds. A new
explicit fit needs its own researcher-selected bounds. Without the absolute
mass or valley scale the same legacy curve admits infinitely many D values.

A versionless DPB request is interpreted using the historical fields. Do not
mix a legacy signed mass or Fermi-energy input with the explicit density fields
in one request.

**On opening a legacy S or S+ρ session**, immediately request the positive
single-valley |m₁| and both valley multiplicities. The current session file
stores `band1Degeneracy` and `band2Degeneracy`, which can both originate
from defaults of 1. Show saved values for confirmation. The old unit-mass
normalization used in the relative carrier plot does not supply |m₁|.
Perform the conversion only when the researcher supplies the mass and
confirms both multiplicities. Cancel leaves the current workspace intact.
On success, store the original E_F and inputs alongside the researcher-confirmed
values and derived D. Open the converted state with fresh explicit bounds;
display old fit results with their original parameterization.

For a legacy Hall fit, use the absolute mass from the parameter vector being
converted and its accompanying multiplicities. Do not combine a starting
mass from one vector with final fitted energies from another. If the saved
scale is incomplete, request the missing values before conversion.

The explicit fit holds the researcher-supplied D, configuration and
multiplicities fixed. The researcher supplies m₁ in S and S+ρ. For an
S+ρ+Hall fit with free m₁, changing its trial value requires solving μ again
and updating the predictions for all three observables. Verify all stage
residuals at the returned parameter vector. The historical conditional Hall-only
m₁ update cannot be reused as an independent amplitude step at fixed D. If all masses are multiplied by c
and D by c^(3/2), μ and the reduced occupations are unchanged: S alone
cannot identify both scales. Never infer a material-specific density,
degeneracy or bounds from the sign of S. Use manual starts for each branch
until a guess model has evidence for that branch and parameterization.

## Integration and acceptance

1. Implement the explicit per-band equations once and call them from forward
   calculations and fitting. Keep the selected configuration fixed through
   every trial. Record the distinction between incompatible density and a
   numerical failure per [P15](https://github.com/pdasya/seeband-web/issues/106)
   and [P16](https://github.com/pdasya/seeband-web/issues/107).
2. Round-trip the complete representation in API, session, saved results and
   export. Include parameterization and all physical inputs in request/cache
   identity. Show E(k) with the correct curvature, offset, single-valley mass
   and labels for each band. Preserve reproducibility of older results.
3. Exercise all 27 combinations of three configurations, acoustic/disorder/
   ionized scattering, and S / S+ρ / S+ρ+Hall. Use synthetic curves with
   researcher-provided bounds. Compare every observable available in that
   mode at the returned parameters, including synthetic CB+CB fits. Include
   nonunit masses and valleys, swapped labels, intrinsic compensation, invalid
   inputs and the SPB limit. Keep mixed scattering (#249) and Kane outside
   this matrix.
4. Document the validated changes in the conventions, changelog and exported
   core version. Independent physical review and human physicist confirmation
   are separate release checks.

## Reproducing the design checks

Run the reference script from the repository root in the project Python
environment. It uses independent SI quadrature for the carrier densities
and illustrative relaxation-time moments for transport. The legacy
comparison calls the current core directly and exercises its band-resolved
concentration output.

```sh
PYTHONPATH=packages/seeband_core/src python scripts/verify_p18_contract.py
```

The reference script exercises selected temperatures and densities. The production fit matrix in
`packages/seeband_core/tests/test_explicit_dpb_fit.py` separately exercises
all 27 public combinations. It perturbs the mass ratio in every mode and
also the absolute mass in the Hall fits. Each final vector is passed back
through the public calculation entry point to reproduce its curves.

On the base revision, the 15 finite-temperature roots at 100, 300 and 800 K
had a maximum normalized balance residual of 4.03 × 10⁻¹⁵. All 12 invalid
same-type inputs were rejected. The 45 synthetic transport evaluations
satisfied reflection and band-exchange symmetry. The separate depleted-band
test recovered the single-band Hall coefficient for either carrier sign.
In three legacy examples with m₁ = 1.7 mₑ, m₂ = 0.8 mₑ and (N₁,N₂) = (2,6),
the largest difference from the independent root was 6.24 × 10⁻⁵ K and the
largest relative band population difference was 5.41 × 10⁻⁷. These figures
apply to the script's specified points and precision.

Additional reference cases cover mixed bands at offsets of both signs and
magnitude 3 eV. At 300 and 800 K the eight additional roots had maximum
normalized residual 7.89 × 10⁻¹⁵. A second quadrature in momentum gave
chemical potentials within 9.10 × 10⁻¹² K. The production implementation
keeps the inherited constants consistently in its density and transport
kernels; the reference uses the current SI values.

For the verified fitter, a bounded coupled starting-point search uses the
existing S, ρ and Hall stage scales when a free absolute mass or a relative
scattering factor couples stages. Its candidate must improve at least one
stage and preserve the others within their objective audit tolerances.
The sequential solver then checks the original stage objectives and the
uncached predictions at the returned vector. This certifies conditional
numerical convergence. The synthetic tests use identified examples and
nearby starts; full parameter identifiability remains sample-dependent.
