# Ionized impurity power-law transport

Core 0.3.0 offers `acPh`, `dis` and `ionized` in every SPB/DPB fit mode,
including S-only. `acPhDis` is no longer a public model choice. Historical
mixed-scattering functions and reference captures remain for reproduction;
their inputs must not be relabelled as ionized impurity results.

## Approximation and conventions

The scientific owner selected isotropic 3D parabolic bands with a scalar
relaxation time tau(E) proportional to E^(3/2), measured from the band edge.
Its amplitude is temperature independent. There is no screened Coulomb
logarithm, dielectric model, impurity-ionization calculation or fitted exponent.
A successful fit therefore does not establish which scattering mechanism a
material actually has.

Write tau(E,T) proportional to T^beta E^(lambda-1/2). Acoustic phonons use
lambda=0, beta=-1; alloy disorder uses lambda=0, beta=0; the ionized
approximation uses lambda=2, beta=0. The general longitudinal temperature
factor is T^(lambda+1+beta). Scattering metadata are immutable and transport
moments receive lambda explicitly; requests never change a global exponent.

Use unnormalised Fermi integrals F_j(eta)=integral x^j/(1+exp(x-eta)) dx.
For a band with mass sign s, eta=s*(mu_K-edge_K)/T. Energies with suffix K
are energies divided by k_B. e is the positive elementary charge.

## Single-band ionized expressions

With t=T/(300 K), the free normalization A has units S/m:

- sigma=A*t^3*F_2(eta), rho=1/sigma.
- S=-s*(k_B/e)*[4 F_3/(3 F_2)-eta], in V/K.
- L=(k_B/e)^2*[5 F_4/(3 F_2)-(4 F_3/(3 F_2))^2].
- kappa_e=L*sigma*T, in W/(m K).
- R_H=-s*[3*pi^2*hbar^3/(e*(2*k_B*m_e)^(3/2))]
  _T^(-3/2)_|m|^(-3/2)*(1/2)*F_(7/2)/F_2^2, in m^3/C.

The Hall moment contains tau squared: its Fermi order is 2*lambda-1/2,
not lambda-1/2. The coefficient is (2*lambda+1/2)/(lambda+1)^2.
Mass m is in electron-mass units; the SPB convention retains the reference
single-valley mass used by the existing model.

## Double-band composition

Retain public R and N=N2/N1, with internal r=R/N. The free B is a relative
conductivity normalization, absorbing microscopic mass and scattering
prefactors; it is not an impurity-density ratio.

sigma_1=A*t^3*F_2(eta_1), sigma_2=A*t^3*(B/|r|)*F_2(eta_2).
Sum sigma=sigma_1+sigma_2, rho=1/sigma, and w_i=sigma_i/sigma.
Then S=w_1*S_1+w_2*S_2 and R_H=w_1^2*R_H1+w_2^2*R_H2.
Hall keeps the existing reference valley convention: the second-band mass
normalization is r*m1*N^(5/3), equivalent to the N^(-5/2)*|r|^(-3/2)
factor relative to band 1. Carrier statistics and root certification do not
change with the scattering choice.

Open-circuit electronic thermal conductivity includes the bipolar term:

kappa_e=T*(L_1*sigma_1+L_2*sigma_2)
+T*sigma_1*sigma_2/(sigma_1+sigma_2)*(S_1-S_2)^2.

The plotted Seebeck contributions are w_i*S_i, rather than each band's
standalone S_i. Carrier densities without Hall remain relative reference values.

## Fitting and starting estimates

Ionized fitting uses verified-sequential-v2 with the existing absolute stage
objectives and bounds. Explicit legacy requests are rejected, without fallback.
SPB numerical estimates use the selected mechanism. DPB neural estimates are
unavailable for ionized because the supplied networks were trained under a
different transport law; users supply starts manually.

The same predictions supply curves, measured-temperature residuals and fitting.
Fermi-window moments are centered to avoid cancellation in degenerate S and L;
scaled Boltzmann tails retain ratios before exponent underflow. Tests compare
independent adaptive quadrature and physical limits, as well as band-sum,
sign, normalization and interleaved-mechanism behavior. Historical captures
remain compatibility evidence, not validation of this new approximation.
