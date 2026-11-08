# Model conventions

The public site is not implemented yet. Carry this text into its Conventions page.

## Single Kane band

SKB jointly fits S(T), rho(T) and signed R_H(T). It assumes one isotropic
nonparabolic band, acoustic phonons, constant density, fixed gap and valley count.
It excludes minority carriers and freeze-out. The common signed band_mass sets total DOS mass and carrier type, fermi_energy
is the signed T=0 energy in K, and A is the SPB acoustic scale. N1 is the common
degeneracy control; valley mass is abs(band_mass)/N1^(2/3). Only kane_gap_ev is new.
Spin is already included.

Chemical potential is relative to the active edge: mu-Ec for electrons, mu-Ev for
holes. Eta is the reduced carrier potential with opposite sign for holes. E(k)
uses the same edge. Constant n(T) is an assumption, not an independent extraction.
Input tables use K, V/K, ohm m and m^3/C; controls label their parameter units.
Thermal conductivity measurements are not needed. Convergence alone does not
establish applicability. See [the core model document](../../packages/seeband_core/docs/kane-model.md)
for equations, numerical domains, weights and validation.
