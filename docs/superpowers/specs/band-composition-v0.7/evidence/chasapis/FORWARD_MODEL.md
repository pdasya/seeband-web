# Chasapis PbSe forward calculation

`forward_model.py` evaluates the supplied preprint's Eqs. (4)--(9), with
Table I temperature laws and Eq. (18) fixed total hole density. It is an
independent evidence calculation, outside production SeeBand. The [comparison](METHOD.md) profiles the conductivity ratio against both measured curves.

Source: _Understanding the role and interplay of heavy hole and light hole
valence bands in the thermoelectric properties of PbSe_, Chasapis et al.; [source PDF](https://arxiv.org/pdf/1502.01087). Page numbers below are the
one-based PDF pages, matching printed labels. Source SHA-256:
`f04997ac2120fed0bd13cfe98b211ba3adf39c2c4c73cbb48417d454c48669a6`.
Runtime: NumPy 2.5.4, SciPy 1.18.1 (repository `.venv`). Fast native PDFium extraction
was used; Eqs. (4), (5), (6), (8), (9), (14), Table I and the adjoining text were
checked against rendered original pages 6, 7, 12, 40. The p.25 mass caveat was
read from native text; no uncertain mass law is implemented.

- Gap: `0.17 + 3e-4*T` eV; valence offset: `0.32 - 2.2e-4*T` eV.
- L total DOS mass: `0.18 + 3e-4*T` electron masses; Sigma total DOS mass: 2.5.
  The masses include valley counts 4 and 12 already; adding those factors again
  would double-count states. L anisotropy K=1.75; Sigma K=1.
- Both carriers are holes: S and RH are positive. Hole kinetic energy is
  measured inward from each valence maximum. `eta_sigma=eta_l-offset/(kB*T)`.
- Fixed total densities: x=.01: 1.8e20, x=.02: 4.7e20, x=.03: 7.6e20 cm^-3.
  Eq.18 uses low-temperature apparent Hall densities; these are distinct from
  Table II room-temperature Hall densities and true per-band concentrations.
- Eq.4 generalized integrals use the derivative Fermi measure. The energy
  polynomial is `x+alpha*x*x`, and the scattering denominator is
  `(1+2*alpha*x)^2+2`. Here alpha is `kB*T/Eg`, dimensionless.
- `g_l=J0` and `g_sigma=F0=log(1+exp(eta_sigma))` follow TDD section 15.2.
  The paper instead uses the generalized integral for both bands; its Sigma
  integral is F0/3. Thus `sigma_L/sigma_Sigma=3*f0*g_l/g_sigma`, and SeeBand's
  Sigma/L conductivity-prefactor ratio is `w2=1/(3*f0)`. The direction and the
  factor three both matter. `combine` implements the paper's S and weak-field
  RH mixtures; `f0` is not a mobility ratio or a direct conductivity fraction.

`forward(T, density)` returns 1D NumPy columns, including per-band S in uV/K,
RH in cm^3/C, populations in cm^-3, reduced chemical potentials and conductance
shapes. SI constants are used internally; division of m^-3 by 1e6 gives cm^-3,
and RH then follows directly as A/(e*p_cm3). Each point independently solves
neutrality; no state propagates between temperatures.

`forward(T, density, freeze_structure_at_k=300, anisotropy_l=1)` holds gap,
offset and masses at 300 K, while actual T still sets occupations and kBT/Eg.
This is the requested sensitivity to fixed TDD parameters. Set K=1 for the
isotropic TDD Hall convention; retain K=1.75 for comparison with the paper.
The anisotropy factor relative to isotropic Hall is 0.9722222 and leaves S,
populations and transport shapes unchanged.

The Table I heavy mass is retained for **all three** densities. The authors
explicitly report on p.25 that x=.03 needs a temperature-dependent heavy mass
to reproduce its Hall maximum. The printed derivative law lacks an adequately
unambiguous normalization/unit prescription for this reconstruction. Therefore
this baseline must not be described as an exact reproduction of their x=.03
best fit. No deformation potential or absolute conductivity is inferred here.
No electrons, bipolar conduction, impurity scattering or explicit interband
scattering are added. Acoustic scattering over the entire 10--900 K calculation
is an extrapolation at low T, where the paper itself notes other mechanisms.

Numerics: SciPy adaptive quadrature, Fermi window +/-55 kBT, separately scaled
minority integrals, and bracketed scalar neutrality solve. The checked range is
10--900 K for the three densities above. The low-temperature minority RH may
be extremely large, while its density and conductance are extremely small.
Neutrality residual is checked against 2e-10 relative error. Quadrature
refinement and reordered temperatures verify the result does not depend on
temperature sampling. `python forward_model.py` runs the focused checks:
nondegenerate acoustic Hall limit 3*pi/8, thermopower limit (kB/e)*(2-eta),
parabolic g=exp(eta)/3 limit, independently integrated occupied density,
fixed neutrality, positive hole signs, correct prefactor conversion, frozen
structure, Hall anisotropy, and observable refinement for all three densities.
