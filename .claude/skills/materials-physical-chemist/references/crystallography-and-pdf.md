# Single crystals, Laue and local structure

## Crystallographic conventions

State cell setting, lattice parameters, space-group symbol/number and origin where needed. Distinguish plane (hkl), plane family {hkl}, direction [uvw] and direction family <uvw>. A direct-lattice [hkl] vector is not generally normal to plane (hkl) outside special metrics. State whether reciprocal vectors include 2 pi; keep orientation matrix, sample axes and instrument coordinates explicit.

CIF symmetry and occupancies describe a model. Check composition, Z, density, Wyckoff multiplicities, interatomic distances and occupancy sums. Similar lattice parameters or space-group labels do not establish identical phases or ordering.

## Laue diffraction

Specify transmission versus back-reflection, white-beam spectrum, detector distance/tilts/centre, reference frame and candidate cell. Index several noncollinear reflections, compare predicted and observed spot positions and verify the inferred orientation using further spots or a controlled rotation.

Conventional white-beam spot positions usually determine orientation and metric ratios but not the absolute lattice scale without energy information or an independent constraint. Quantitative strain analysis requires a calibrated geometry and the appropriate energy/strain constraints; distinguish relative deviatoric strain from absolute hydrostatic strain.

Split/streaked spots may reflect multiple grains, twins, mosaicity, strain, bending or instrument effects. One good pattern samples one illuminated region; it does not demonstrate whole-boule homogeneity, chemical purity or absence of twins. Merohedral twins can have overlapping reciprocal lattices. Use spatial scans, rocking/rotation data, reciprocal-space mapping, EBSD or TEM according to domain scale and suspected twin relation.

## Single-crystal XRD (SC-XRD)

Follow raw frames → indexing/integration → corrections/scaling → symmetry assessment → structure solution → refinement → validation. Record wavelength, temperature, crystal dimensions, completeness/resolution, redundancy, integration/absorption method and merging statistics. Inspect split reflections, multiple lattices, overloads, weak superstructure reflections and diffuse scattering before merging away evidence.

Select symmetry from metric, systematic absences, intensity statistics, chemistry and model testing together. Test pseudosymmetry and plausible subgroups when physically relevant. For heavy/absorbing intermetallics assess absorption, extinction and fluorescence. Do not infer all atom identities from electron density without chemical constraints.

Report R1/wR2 with reflection selection, goodness-of-fit, data/parameter/restraint counts, occupancies/ADPs and residual density. Model occupancy–ADP–scale correlations and limited contrast explicitly. CheckCIF alerts need resolution or a scientific explanation; a clean report alone does not prove the model. Preserve CIF and reflection data, plus a defensible record of raw frames/processing.

For twins, give twin law, domain fractions with uncertainty, domain treatment and evidence that the model is supported. Absolute-structure parameters require a suitable noncentrosymmetric problem and anomalous contrast; an indeterminate parameter is not evidence of absence of inversion twinning. Protein-specific R-free, ligand omit maps and residue validation are not default requirements for inorganic SC-XRD.

## Atomic pair distribution function (PDF)

Disambiguate atomic PDF from the ICDD Powder Diffraction File and a document format. Atomic PDF uses total scattering, including Bragg and diffuse contributions, to examine pair correlations. An ordinary short-range lab PXRD scan is not automatically a reliable PDF dataset.

Under a common convention:

`F(Q) = Q [S(Q) - 1]`

`G(r) = (2/pi) integral[Qmin,Qmax] F(Q) sin(Q r) dQ`.

Report Q units/range, transform/window convention, composition/scattering weights, background, container, absorption, multiple-scattering/Compton corrections as relevant, and instrument damping/broadening calibration. X-ray and neutron PDFs weight chemical pairs differently. Finite Qmax causes termination effects and a characteristic real-space resolution scale of order `pi/Qmax`; it is not itself an uncertainty on every fitted bond length.

Fit physically motivated models over stated r ranges. Compare local versus extended-r fits and sensitivity to Qmax, background, instrument parameters, ADPs, correlated motion and finite domain size. A visually improved low-symmetry fit with more parameters needs an identifiability/complexity check. PDF peak heights are scattering-weighted and affected by overlap/resolution; do not read them as elemental concentrations directly.

Local distortions can coexist with a high-symmetry average Bragg structure. Check matched sample state/temperature and preprocessing before declaring disagreement. To test alternatives use temperature-dependent PDF and SC-XRD, diffuse scattering, EXAFS or local electron diffraction. Static versus dynamic disorder may require an energy/time-sensitive probe; equal-time pair correlations alone need not distinguish them.

Use [DiffPy documentation](https://www.diffpy.org/doc/pdfgetx/2.2.0/tutorial.html) for processing conventions and [LaueTools](https://lauetools.readthedocs.io/en/latest/) for orientation/geometry workflows. Consult the installed software version before writing commands.
