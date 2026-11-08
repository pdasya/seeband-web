# Single Kane band in the shared band-model framework

`band_models.SkbModel` subclasses `_BandModel`, alongside SPB and DPB. It uses
common parameter descriptions, validation, scales, bounds, fit progress, curve
naming and known-issue handling. `kane.py` contains only numerical transport and
solver functions, analogous to the existing numerical modules. The registry id
is `skb`, mode `skb_s_rho_rh`; it jointly fits S(T), rho(T) and R_H(T).

## Parameters

| Parameter                   | Core meaning                                                                    | Role   |
| --------------------------- | ------------------------------------------------------------------------------- | ------ |
| `band_mass`                 | Signed total DOS mass in electron masses; positive conduction, negative valence | fitted |
| `fermi_energy`              | Signed Fermi energy at T=0 relative to the active edge, in K                    | fitted |
| `A`                         | Existing SPB acoustic conductivity scale                                        | fitted |
| `kane_gap_ev`               | Kane nonparabolicity energy, eV                                                 | fixed  |
| request `band_1_degeneracy` | Existing N1 degeneracy control, excluding spin                                  | fixed  |

The first three descriptions are reused from SPB S+rho, with mass fitted when
Hall data are present. `band_mass` retains its .01 control/display/core scale;
fermi_energy and A retain their existing units and scales. The gap alone is a
new parameter: integer control units with .01 eV scaling, through `model_scales`.
No separate density, mobility, carrier-sign or valley-count parameters exist.

A one-band description sets `Degeneracy(1, None)`, using the common N1 field
without presenting an unused N2 field. The second request degeneracy stays 1.
N1 accepts a positive effective degeneracy, following the existing framework.
The mass is total m_DOS; single-valley mass is abs(band_mass)/N1^(2/3).
Changing N1 at fixed DOS mass affects valley mass and E(k), not transport curves.

## Assumptions

One spherical isotropic band, acoustic phonons, constant gap and mass, equivalent
valleys and fully ionized constant net doping. Minority carriers, freeze-out,
impurity scattering and three-band transport are excluded. Hall sign changes
cannot be fitted. This reconstructs an effective band near its edge, not the
full Brillouin-zone band structure. Eg is supplied independently. Convergence
alone does not establish applicability to a particular sample.

## Equations

Let s=sign(band_mass), m=abs(band_mass)*m_e, E0=kB*abs(fermi_energy), Eg in joules.
The Fermi energy must lie within the active band: band_mass*fermi_energy > 0.

```text
n0 = [2 m E0 (1+E0/Eg)]^(3/2)/(3 pi^2 hbar^3)
```

This is the framework's constant-doping T=0 convention with Kane dispersion,
not a rename of density as Fermi energy. At each T solve n(T,eta)=n0.
For x=E/(kBT), alpha=kBT/Eg, w=exp(x-eta)/(1+exp(x-eta))^2,
u=x+alpha*x^2, v=(1+2*alpha*x)^2+2, integrate from 0 to infinity:

```text
a = integral w u/v dx;     b = integral w x u/v dx
c = integral w x^2 u/v dx; d = integral w sqrt(u)/v^2 dx
g = integral w u^(3/2) dx
n(T,eta) = (2 m kBT)^(3/2) g/(3 pi^2 hbar^3)
S = -s (kB/e) (b/a-eta)
L = (kB/e)^2 [c/a-(b/a)^2]
A_H = d g/a^2
R_H = -s A_H/(e n0)
sigma = 3 A a; rho = 1/sigma
mu_drift = sigma/(e n0); mu_H = A_H mu_drift
chemical_potential_k = s eta T
```

The factor 3 in sigma makes `A` the existing acoustic parameter: as Eg tends to
infinity, a tends to F0/3 and sigma tends to A*F0, exactly SPB's convention.
Concentration and mobility are outputs, not independent fit parameters.
Chemical potential is mu-Ec for electrons, mu-Ev for holes, in K. Multiplying
by kB/e gives eV; its arbitrary absolute energy origin is not inferred.

For valley mass m_b=m/N1^(2/3), dispersion obeys
E(1+E/Eg)=hbar^2*k^2/(2*m_b). The E(k) chart uses positive electron or negative
valence-band energy, relative to the active edge at zero.

## Fitting

The numerical joint solver populates the existing `FitProgress.stage_fits`
under `joint`. `_BandModel` handles result status, covariance errors, physical
bounds, failure logging and flags. Optimization keeps the selected carrier
branch and fits log(abs(band_mass)), log(abs(fermi_energy)), log(A). Bounds
are still expressed in signed physical core units. Bounds spanning zero are
intersected with that branch; the solver's positive lower floor is 1e-12.
The default bounds are mass [-3,3], Fermi energy [-3000,3000] K, A [1,1e7].

Each curve has equal total residual weight, on its original temperature grid:

```text
r_S = (S_model-S_data)/max(RMS(S_data),1 microvolt/K)/sqrt(N_S)
r_rho = log(rho_model/rho_data)/sqrt(N_rho)
r_RH = log(abs(RH_model)/abs(RH_data))/sqrt(N_RH)
```

Signs are validated before logs. At least three points per series are required.
Weights are engineering defaults, not measured uncertainties. There are at most
300 function evaluations; the common worker provides process cancellation.
Local covariance errors are conditional on fixed gap/N1 and the model. A
Jacobian singular-value ratio <=1e-8 omits errors and adds `skb_weak_fit`.
Results at bounds are marked by the common adapter. The known-issue registry
also supplies `skb_assumptions` and the shared extrapolation flag.

## Numerics and curves

Centred moments avoid cancellation in L. Gauss-Legendre uses x=t^2, 64 nodes per
segment, splits at eta and eta +/-16, and window
[max(0,eta-60),max(80,eta+60)]. Stable scaled weights protect integral ratios.
Brent solves log-density with eta tolerance 2e-10 and 100 steps. Supported eta
is [-80,10000], alpha [0,100]; roots outside fail without clipping. These choices
are checked against independent quadrature, not claimed as universal tail bounds.

`measured` returns exactly S, rho, R_H, like other band models. Chemical potential
uses `chemical_potential_k`. Concentration uses existing
`carrier_concentration_by_band` with `carrier_concentration_band_1_per_cm3`.
Other kinds select L, eta, mobility, Hall factor, masses and conductivity.
`band_structure` returns k in `wavevector_per_m`, E in `band_energy_ev`, and
empty `temperature_k`; the browser labels k in inverse angstroms. Constant n(T)
and band-edge masses follow the model assumptions. No lattice heat flow or zT
is calculated.

Transport: Lin & Liu, Scientific Reports 12, 7056 (2022),
[doi:10.1038/s41598-022-09734-4](https://doi.org/10.1038/s41598-022-09734-4), eqs. (1)-(14).
Dispersion: Askerov (1970), pp. 38-40, eq. (5.14), with its light-mass/two-band
approximation. Three-band eq. (5.16) requires a separate transport derivation.

Tests check physical limits, independent DOS integration, published Table 1
mass, synthetic global fits for both carrier types, exact conversion from the
initial density/mobility SKB prototype, and the SPB parabolic limit with the
same A and signed Fermi-energy conventions. API/browser tests cover real workers,
common fields and temperature/dispersion charts.

The four chart panels offer all SKB derived quantities independently. The shared
`band-diagram` endpoint uses the same Kane dispersion for SKB, with energy in kelvin
and wavevector in inverse metres; the band diagram displays a schematic axis without
ticks. The separate E(k) choice shows the physical axes in Å⁻¹ and eV.
