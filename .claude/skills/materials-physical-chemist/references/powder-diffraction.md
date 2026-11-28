# Powder diffraction: observation to phase and microstructure

## Establish what was measured

Record radiation/wavelength or energy, geometry (reflection, transmission, capillary, grazing incidence), angular or Q range, step and counting scheme, optics/detector, sample preparation and temperature. Preserve intensity uncertainties, background/holder scans, calibration standard and raw data when available. A screenshot supports qualitative discussion, not a new precision refinement.

Identify whether the requested result is phase identification, cell determination, structural refinement, quantitative phase analysis, line-profile analysis, texture or residual stress. These need different models and data quality.

## Positions and indexing

Use `2 d sin(theta) = n lambda`; the recorded powder angle is usually `2 theta`. Declare units and the wavelength convention (e.g. K-alpha1 versus unresolved doublet). With `Q = 4 pi sin(theta)/lambda`, use `Q = 2 pi/d` for a first-order indexed reflection.

Check sample displacement, zero offset, wavelength, transparency and calibration before assigning a peak shift to lattice expansion or chemical substitution. Displacement and zero offsets have different angular dependence; do not treat all shifts as a constant. For a noncubic lattice use the reciprocal metric tensor. Extinctions constrain space-group candidates but overlap, weak peaks and texture can hide discriminating reflections. Indexing a cell alone does not solve the atomic structure.

Search plausible phases from the elements, synthesis history and reference structures. Compare the whole profile, including weak/unindexed reflections, not only the strongest peaks. Record database entry and original publication; a computed reference pattern is a prediction from its structural model.

## Refinement and quantitative analysis

Le Bail/Pawley extraction fits cell/profile and reflection intensities without establishing atomic positions. Rietveld uses a structural model; it is not proof that this model is unique.

Start with calibrated instrument/geometry and a chemically justified phase list. Establish background, scale, lattice and profile before freeing less identifiable atomic parameters; adapt the order to correlations rather than following a rigid ritual. Assess:

- Observed/calculated/difference profiles over the full range, reflection markers, residual structure, Rwp and goodness-of-fit with their weighting/error definitions.
- Correlations among scale, occupancy, displacement parameters, absorption, texture and background; physical ADPs, occupancies, distances and charge balance.
- Preferred orientation, particle statistics, anisotropic broadening, stacking faults, absorption/microabsorption and fluorescence. A fitted correction cannot replace representative specimen preparation.
- The number of independently supported parameters and stability against plausible backgrounds, ranges, starting models and remounts. Fit covariance describes precision conditional on the model, not all systematic uncertainty.

For conventional crystalline QPA, scale-factor phase fractions require appropriate crystal contents and normalization. Report mass/mole/volume basis. Fractions normalized over modeled crystalline phases do not quantify an unmodeled amorphous fraction. An appropriate internal/external standard or other calibrated method is needed when the amorphous fraction matters; assess microabsorption and standard mixing effects. Do not assign a universal impurity detection threshold.

Occupancy refinement needs scattering contrast and sufficient independent information. Similar X-ray scattering factors, correlated ADPs and heavy/light atom contrast can prevent a reliable stoichiometry determination. Use composition constraints or complementary neutron/chemical data when they resolve the ambiguity.

## Coherent domain size, strain and defects

For the Scherrer estimate `L = K lambda / (beta cos(theta))`, state the shape factor K, reflection, breadth definition (FWHM or integral breadth), and beta in radians of `2 theta`. Correct for instrumental broadening with a compatible line-shape model. Gaussian breadths combine in quadrature; Lorentzian breadths add; arbitrary subtraction is not general.

L is an apparent coherent domain dimension along the scattering vector under the assumed model. It is not automatically a particle diameter, an EBSD grain diameter or an isotropic size distribution.

A simple isotropic Williamson–Hall convention is `beta cos(theta) = K lambda/L + 4 epsilon sin(theta)`. Its strain parameter depends on breadth/model conventions. Use it as a screening model only when several suitable reflections and instrument correction support it; anisotropy, dislocations, faults, overlapping peaks and texture can invalidate a single straight line. Avoid forcing a positive size/strain split from uninformative data.

## Worked cross-method interpretation

An annealed intermetallic has no extra PXRD peaks, Rwp = 4%, a Scherrer estimate of 35 nm, nominal EDS composition and 12 micrometre EBSD grains.

An appropriate statement is: "No additional crystalline phase was detected in this PXRD measurement. EDS is consistent with the nominal composition within its analytical uncertainty. EBSD resolves micrometre grains; line broadening gives an apparent nanometre coherent-domain scale under the size-broadening model."

Check instrument broadening and strain/fault contributions before treating 35 nm as real substructure. Inspect full-profile residuals and representative BSE/EDS regions for secondary phases; report EBSD grain definitions and sampling. If the disparity remains, use TEM/subgrain characterization to test it. Each claimed quantity now has an observable, a model and a limitation.

For refinement practice see [IUCr guidelines](https://journals.iucr.org/j/issues/1999/01/00/gl0561/). For the adapted skill foundations see [sources](sources-and-attribution.md).
