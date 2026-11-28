# Electron microscopy and microanalysis

## Common intake and sampling

Establish material, scientific question, preparation history, orientation/cross-section, coating/mount, instrument/detector, accelerating voltage, current, working distance, acquisition time/dose and calibrated pixel/scale information. Ask for raw spectra/patterns when quantitative reanalysis depends on them. A displayed colour map or image does not contain all the original analytical data.

Choose representative locations and independent specimens/batches for the claim. Record field selection and distinguish pixels, grains, fields, lamellae and samples as statistical units. Spatially correlated pixels are not independent replicates. Compare methods at compatible sampling scales and states.

## SEM: morphology and contrast

SE contrast is strongly affected by topography and charging. BSE contrast can reflect composition, orientation/channeling and topography; bright regions are not automatically a particular heavier-element phase. Use polished cross-sections, complementary spectra/maps and appropriate detector geometry to test assignments.

Check charging, drift, edge enhancement, polishing relief, pull-out, scratches and contamination before calling pores, precipitates or grain boundaries. Report 2D section size distributions and segmentation definitions; converting to 3D particle/grain distributions requires stereological assumptions. Preserve scale calibration and note any image resampling.

## EDX/EDS and EPMA/WDS

EDX and EDS refer to energy-dispersive X-ray spectroscopy here. Standards-based calibrated EDS can be quantitative; its accuracy depends on matrix, preparation, line selection, standards, detector performance and corrections. Do not dismiss EDS categorically as qualitative, or treat standardless normalized numbers as exact stoichiometry.

For compositional claims check:

- Excitation energy/overvoltage for chosen lines, interaction volume, take-off geometry, sample thickness/roughness, absorption/fluorescence and matrix corrections. Select voltage for the analytical task rather than a universal kV rule.
- Peak overlap and deconvolution, background, dead time/pile-up, counts and drift. Inspect spectra behind elemental maps; a fitted colour map can contain overlap artifacts.
- Coating, substrate, holder, polishing residue and FIB cap/implantation contributions. SEM EDS chemical resolution is not simply the SEM image pixel size; thin-foil STEM EDS is also thickness/dose dependent.
- Atomic versus weight percent, normalization and raw analytical totals, omitted elements, uncertainties and standards. Detectability of light/trace elements is matrix/line/instrument dependent; EDS cannot measure hydrogen and does not generally establish valence or crystallographic occupancy.

Use EPMA/WDS when its spectral resolution and calibrated local quantification resolve a consequential ambiguity; use appropriate bulk chemistry for a bulk-composition claim. No technique is automatically definitive without sample preparation and validation. Consult [NIST on quantitative EDS](https://www.nist.gov/publications/electron-excited-x-ray-microanalysis-energy-dispersive-spectrometry-50-analytical).

## EBSD: orientations, phases and grains

Record geometry/pattern-centre calibration, phase files/symmetry, step size, pattern resolution/binning, indexing method, quality thresholds and acquisition settings. Inspect raw patterns and fit quality for pseudosymmetry, phase overlap, surface deformation and mixed patterns at boundaries. Phase indexing alone may be ambiguous between structurally similar phases; combine chemistry or better diffraction where useful.

For grain statistics report reconstruction misorientation threshold, minimum pixels/area, treatment of nonindexed points and edge grains, cleanup/interpolation, area/number weighting and grain-size definition. Choose step size and field size to resolve the target population, then assess sensitivity; no universal step size guarantees accurate statistics.

Report IPF reference direction/key, boundary definitions and map quality. Differentiate orientation spread, local misorientation (KAM/GOS) and elastic strain. KAM is affected by step size, kernel, noise and boundaries and is not directly an absolute dislocation density. GND estimates need spatial-gradient/dislocation assumptions and cannot recover all statistically stored dislocations; elastic-strain claims require an appropriate calibrated method such as HR-EBSD.

Two-dimensional grain maps are not automatically three-dimensional bulk grain distributions. Unresolved nanodomains or overlapping twin patterns can escape conventional indexing. See [MTEX grain reconstruction](https://mtex-toolbox.github.io/EBSD.calcGrains.html) for software definitions.

## TEM/STEM: local structure, defects and chemistry

Record lamella origin, thinning/FIB/ion-milling conditions, thickness estimate, accelerating voltage, imaging/diffraction mode, convergence/collection geometry and dose history as relevant. Assess implantation, amorphization, redeposition, preferential sputtering, oxidation and beam-driven changes. Low-energy final preparation can reduce some artifacts but does not prove they are absent.

For SAED/NBED/CBED index several reflections and zone axes with calibrated camera geometry. Electron diffraction is often dynamical; multiple scattering, double diffraction and thickness can generate apparent forbidden spots. A single d-spacing does not uniquely identify a phase.

HRTEM contrast depends on defocus, thickness, aberrations and orientation; atomic-looking contrast is not a direct atom map without an imaging model. HAADF intensity depends on composition together with thickness/channeling/geometry; combine simulations and spectra when assigning site chemistry. EELS oxidation-state assignments require energy calibration, thickness/background treatment and appropriate reference/edge interpretation.

For defects apply the relevant imaging/visibility model and report its limits; one micrograph need not determine a unique Burgers vector or defect density. Repeat across suitable areas/orientations and compare to bulk methods before making a bulk claim from a small lamella.
