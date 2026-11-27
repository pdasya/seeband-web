# Why the PbTe doping order differs at 700 K

Source: Pei et al., Nature 473, 66–69 (2011), doi:10.1038/nature09996, Fig. 1, Eq. 3 and SI Sec. 2, Figs. S3(b), Eqs. S1–S2. [SI at Caltech](https://authors.library.caltech.edu/records/r4cjr-qn161/files/nature09996-s1.pdf). Comparison: Thesberg et al., Phys. Rev. B 95, 125206 (2017), Figs. 5 and 6 and Eqs. 37–39. The published curves are theoretical. The original PDF hashes and digitization details are in the metadata JSON files.

## Conventions

C and L have four valleys, Sigma has twelve. The band-edge DOS masses per family at 300 K are respectively 0.30, 0.36 and 2 electron masses. Using m_b = m_DOS/N^(2/3), the DOS masses per valley are 0.1191, 0.1429 and 0.3816. The ordinary spin degeneracy is already included in the 3D density integral. For K = m_long/m_trans = 3.58, 3.58 and 1 respectively, use m_trans = m_b/K^(1/3), and m_cond = 3/(2/m_trans+1/m_long). These mass conversions assume equivalent aligned-by-symmetry ellipsoids in a cubic material.

## Calculation without adjustable parameters

All cases are three parabolic bands with SeeBand core 8c6fafc, acoustic intraband scattering, and a common chemical potential relative to the conduction edge; net holes are held fixed. The carrier density contains m_DOS^(3/2) once. In the explicit-valley cases conductivity is proportional to N*F0(eta)/(m_cond*D²), for intravalley deformation-potential scattering into the same valley. This weight follows from the transport approximation; it is not a measured band mobility. Pei used Kane L and C and parabolic Sigma. The controlled comparisons do not purport to implement every term of that theory.

Four cases in bands.csv isolate changes. 'previous' reproduces the original scalar-mass calculation. 'valleys' only corrects the conductivity weights. 'Pei_edges' also sets E_C−E_L = 0.18 + 0.0004 T eV, for pure PbTe, instead of Thesberg's 0.09 + 0.0004 T. Both have E_C−E_Sigma=0.36 eV. 'Pei_PB' additionally applies Pei's logarithmic mass slope (T/300)^0.5 for C and L. The earlier cases use Thesberg Eq. 38. Deformation potentials are 19 eV for C and L and 9.5 eV for Sigma. Adjacent stages retain all other inputs. The CSV includes conductivity weights, populations, band Seebecks, and separate intrinsic, hole–hole and electron–hole Lorenz terms. L units: 10^-8 W ohm K^-2. The direct combined moments and the grouped variance are checked independently for equality, with neutrality checked at every root.

## Independent reference constraints

Pei SI Fig. S3(b) plots the heavy-hole fraction of holes and total conductivity. No separately identifiable published electron and light-hole conductivity curves are given in that inset. published-and-inferred.csv contains the digitized Sigma conductivity and a chemical potential inferred from p_Sigma = (p_Sigma/p_total) p_total using the stated parabolic Sigma DOS of 2 m_e and edge −0.36 eV. This inference interprets the concentration labels as total holes, while the forward-model input is fixed net holes; it is not an independent measurement of mu. Dashed/solid lines are the previous/Pei_PB model; circles use the printed curves or the Sigma density inversion. SI prose for the 2%-Na PbTe (~2.4e20 cm^-3) gives a conflicting 400 K anchor: f_L~0.77 and mobility ratio b~4 imply heavy-hole conductivity fraction ~0.069 in a two-hole-band treatment, versus 0.475 on the inset's 2.5e20 line. Keep these as separate constraints. Do not use them both for calibration.

The Fig. 5/6 crosscheck samples fixed _energies_ in Thesberg. At 850 K the red marker in 5(b) gives ~2.9 and the blue marker in zoom 5(c) gives ~2.21, while the text attributes ~2.9 to the blue doping in Fig. 6. The fixed-energy slices and fixed-density trajectories need not coincide, so this discrepancy does not establish a legend swap.

## Replay

With seeband_core installed from the above revision and numpy/scipy, run python replay.py and python infer_mu.py. Then run python plot.py (matplotlib/pandas). To repeat the PDF extraction use python inset/extract.py PEI_SI.pdf (pdfplumber) and python ../formula-audit/crosscheck.py THESBERG.pdf (pypdfium2); the raw sources can be fetched from Caltech or https://www.iue.tuwien.ac.at/pdf/ib_2017/JB2017_Thesberg_1.pdf . No fitting, weights inferred from matching reference curves, or production code changes.
