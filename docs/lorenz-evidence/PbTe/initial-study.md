# PbTe Lorenz number compared with Thesberg et al., Fig. 6

Figure 6 in [Physical Review B 95, 125206 (2017)](https://doi.org/10.1103/PhysRevB.95.125206) is a theoretical prediction. Experimental points in Fig. 5(a) concern Seebeck coefficient and resistivity. This comparison does not establish agreement with a measurement of L.

## Replay

1. Use the [original PDF](https://www.iue.tuwien.ac.at/pdf/ib_2017/JB2017_Thesberg_1.pdf) (hash in digitize-record.json). Run `python digitize.py /path/to/pdf` with pypdfium2 5.15.2, or use the included reference.csv.
2. With [SeeBand core at 8c6fafc](https://github.com/pdasya/seeband-web/tree/8c6fafcd54c090c37feae6265108b7d94a4d4570), run `uv run python /path/to/compare.py`. This calls the production single-band acoustic transport moments and Fermi integral, assembled externally for three bands. No production three-band API or fitting is used.
3. Run `python plot.py` with NumPy, pandas and Matplotlib. All outputs are written beside the script. Plot and summary residuals use the density scenario. Units of all Lorenz columns are 10⁻⁸ W Ω K⁻². The weighted columns add up to intraband; the final total is intraband + hole_hole + bipolar.

## Inputs and conventions

- Isotropic parabolic C, L and Sigma. No interband scattering. Edges relative to C: 0, −(0.09 + 0.0004 T), −0.36 eV. At 300 K the masses for C, L, Sigma are 0.3, 0.36, 2 electron masses. For C and L multiply by 1 + 0.5 (T−300)/T. Deformation potentials 19, 19 and 9.5 eV, respectively.
- Conductances are proportional to Nᵢ F₀(ηᵢ)/(mᵢ Dᵢ²) for intravalley acoustic scattering (Eqs. 10–14); common prefactors cancel. The density calculation counts two spin states. The paper gives one scalar mass per band, without unambiguously prescribing an additional valley factor for this calculation.
- Primary scenario “density”: one effective channel for each printed mass; at every T solve p_L + p_Sigma − n_C = specified net doping. “density_valleys” illustrates the different assumption that these are single-valley masses with N_L=4, N_Sigma=12, N_C=4. “figure_mark” instead holds each Fig. 5(c) vertical energy marker fixed relative to C; the column net_holes_cm3 shows that this does not hold density constant. Neither sensitivity run is fitted.
- Decomposition: wᵢ = σᵢ/Σσ, w_h = w_L+w_Sigma, S_h = (w_L S_L+w_Sigma S_Sigma)/w_h. The within-hole-group term is w_L w_Sigma (S_L−S_Sigma)²/w_h. The electron–hole term is w_h w_C (S_h−S_C)². This split assigns the open-circuit conductivity of the combined hole group before combining it with electrons. The script checks its sum against the total formed directly from moments.
- The Fig. 6 solid-minus-dotted difference gives only the sum of the two mixing terms. The paper does not provide individual band weights/Seebeck values as temperature series in this figure.

## Agreement and limitations

PDF page 8 (printed page 125206-8) contains all six paths. We extracted 173 vertices, calibrated on axis ticks; reading envelope about 0.003 in plot units and 0.1 K. This is not an experimental error bar. The solid lines for densities 1.5, 2.0 and 2.5 (×10²⁰ cm⁻³) leave the frame near 847, 799 and 741 K. The star in the comparison is the authors’ approximate off-frame value for the blue curve at 850 K, from p. 9. It is excluded from vertex errors.

For the primary scenario, RMSE evaluated at the visible solid path vertices is 0.449, 0.217 and 0.290 in order of increasing doping. At 700 K the order of the curves with density is reversed. At 850 K and the highest density the primary calculation gives 2.382, compared with the authors’ text estimate of about 2.9. For the middle density the 850 K total becomes 9.162 if the marker is held fixed and 16.948 if the extra valley factors are applied at fixed doping. These are sensitivity calculations, not intervals on a measured value.

The model setup in Sec. II.A.3 specifies three bands, despite the figure caption saying two. The printed Eq. (37) implies L/Sigma crossover at 675 K; the nearby prose quotes about 450 K. The calculation follows the printed equation. The figure is sufficient to test the magnitude and density ordering, but not to identify which input convention causes the residual. Reproduction would benefit from the authors’ μ(T), valley and transport prefactors, or their input files.
