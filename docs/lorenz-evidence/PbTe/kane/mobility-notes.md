# Pei PbTe partial drift mobilities

Run python mobility_audit.py in the extracted directory with NumPy, SciPy, pandas, and matplotlib. replay.py supplies the forward model. ../ref49/inset/fractions_1K.csv is the original curve digitization. The audit does not fit any inputs. Each CSV row reports an independent product of two mass factors, the squared acoustic deformation-potential ratio and a dimensionless transport integral ratio, verified against the forward conductivity/population quotient. T in K, p20 in 10^20 cm^-3. fig_upper assumes zero electron conductivity. fig_lower_reading/fig_upper_reading propagate ±0.005 in both figure fractions at zero electron conductivity (a reading envelope). wC_required is the fractional conductivity electrons would need to reconcile the two fractions with the forward drift ratio. both_family_mass_diagnostic substitutes group masses for pocket masses in both factors to illustrate a convention change, not an accepted correction.

Pei Nature 2011 SI p.3 uses the Hall peak at 400 K, assumed band Hall factors and resistivity to infer mobilities, then estimates deformation potentials. The figure and prose differ at 400 K. With p_L/p_total=0.77 and b=4 the predicted heavy-hole conductivity share is 0.0695; the nearest concentration on the inset gives 0.475. The curve is a calculation, not measured partial mobilities. Relevant sources:

- Pei SI pp. 2–4, Fig. S3 and Eq. S1: https://authors.library.caltech.edu/records/r4cjr-qn161/files/nature09996-s1.pdf
- Bardeen & Shockley (SI ref. 27), acoustic deformation potential and mobility: https://doi.org/10.1103/PhysRev.80.72
- Ravich et al. (SI ref. 20), theory of lead chalcogenide scattering: https://doi.org/10.1002/pssb.2220430102
- Pei et al., independent author clarification of single-valley DOS mass and conduction mass in the acoustic mobility prefactor: https://arxiv.org/pdf/1111.5355
- Kane integral convention: https://doi.org/10.1038/s41598-022-09734-4
