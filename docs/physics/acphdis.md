# Acoustic phonons and alloy disorder in parabolic bands (#249)

## Independent evidence and assumptions

Wang et al. measured the Hall mobility of PbSe–PbS solid solutions. In their equations (6)–(7) the electronic mobility integral contains a combined relaxation time with inverse equal to the sum of the acoustic and alloy inverse times. They used a single Kane band. This example supports the order of operations; its band parameters and dispersion are specific to their material. [Wang et al., J. Phys. D 46, 405301 (2013)](https://doi.org/10.1088/0022-3727/46/40/405301)

Gurunathan et al. applied an alloy transport model to composition-dependent measurements. Equation (10) divides the phonon-limited transport prefactor by a factor of the form $1+\Theta/T$. The alloy term contains the composition-weighted variance of the scattering potential, and the acoustic term contains the deformation potential and elastic modulus. At fixed composition with constant material parameters, $\Theta$ has units of kelvin. Their alloy composition indices describe chemical components. The band indices below describe transport channels. [Gurunathan et al., Advanced Electronic Materials (2022)](https://doi.org/10.1002/aelm.202200327)

## Mapping to the web calculation

For isotropic 3D parabolic valleys, elastic short-range alloy scattering and acoustic deformation-potential scattering in equipartition, take carrier energy $\epsilon\ge0$ from each valley edge. For independent intravalley processes the rates have the common density-of-states factor $\sqrt{\epsilon}$. Writing their sum as $(a_i T+d_i)\sqrt{\epsilon}$ gives $\Theta_i=d_i/a_i$ and the following ratio of mixed to acoustic relaxation times at the same energy and temperature:

$$
f_i(T)=\frac{\tau_{i,\rm mix}}{\tau_{i,\rm ac}}=\frac{T}{T+\Theta_i}.
$$

For the API's dimensionless crossover parameters, $\Theta_1=(300\,\mathrm K)C$ and $\Theta_2=(300\,\mathrm K)D$. Use core values after any desktop control-to-core conversion. At $T=\Theta_i>0$ the channel has half its acoustic conductivity. Setting both crossovers to zero recovers the acoustic law at the same prefactors.

In modes with resistivity, multiply each acoustic channel conductivity by its own $f_i(T)$. The energy-independent factor cancels in each channel's Seebeck coefficient and weak-field Hall coefficient. For parallel channels, the outputs are

$$
\rho=\frac{1}{\sum_i\sigma_i},\qquad
S=\frac{\sum_i\sigma_i S_i}{\sum_i\sigma_i},\qquad
R_H=\frac{\sum_i\sigma_i^2 R_{H,i}}{(\sum_i\sigma_i)^2}.
$$

Thus the explicit DPB band-2 prefactor relative to band 1 is $(N_2/N_1)(B/M)(T+\Theta_1)/(T+\Theta_2)$, with $M=|m_2|/|m_1|$. Each band still has its own reduced chemical potential and transport integral. Equal crossovers preserve the relative conductivity and hence total S and Hall, while scaling resistivity. Different crossovers can change all three curves.

**Desktop S-only convention.** SPB uses its structural Seebeck curve. DPB uses the desktop structural weighting with unit relative scattering prefactor and mass and multiplicity dependence. The editor keeps the resistivity-mode drafts separately. When the two crossovers differ, switching from a fit with resistivity to structural S-only can change the displayed S curve. This is the selected desktop fit-mode convention. The independent papers motivate combined scattering within a band; they do not establish this S-only convention or determine two independent crossovers from S alone.

## Reproduction

The public HTTP moment comparison covers VB+VB, VB+CB and CB+CB at 100, 450 and 800 K. It uses an independent neutrality solve and numerical transport moments. Reflecting all band signs reverses S and Hall and preserves resistivity. On relabelling the mixed pair, the two crossover parameters must also exchange places.

```sh
uv run pytest -q apps/api/tests/test_explicit_dpb_curves.py -k acPhDis
uv run pytest -q packages/seeband_core/tests/test_mixed_scattering.py
uv run python packages/seeband_core/scripts/check_p11_fixed_point.py
```

For a reproducible desktop example with fixed inputs, historical numerical discrepancies and separately evaluated residuals, see the [example-03 comparison](../../packages/seeband_core/docs/dpb-acphdis-weight.md).
