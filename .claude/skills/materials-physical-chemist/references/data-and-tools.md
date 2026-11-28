# Data provenance and computational tools

## Preserve the scientific object

Keep raw instrument/structure inputs separate from processed data and final plots. Record units, column definitions, specimen/batch IDs, preparation/measurement conditions, calibration, masks/exclusions, correction/fit parameters, software versions and uncertainty conventions. Save source IDs/DOIs, retrieval date and database/assessment version for external records. Match processed results to their parent raw data.

For CIF intake inspect symmetry, occupancies/disorder, formula, Z, cell setting and parser warnings. Pymatgen's periodic Structure and nonperiodic Molecule are different objects; distinguish fractional and Cartesian coordinates. Tolerance-dependent symmetry assignment needs declared length/angle tolerances and sensitivity checks when the assignment matters. Preserve partial occupancy/site labels and note representation loss during conversions to formats such as POSCAR or XYZ. Round-trip checks must compare scientifically relevant properties, not just parsing success.

## Choose software for the requested operation

| Operation                                                                                    | Candidate tools; verify installed contracts                                                                                              |
| -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Composition, structure conversion, symmetry, simulated powder patterns, computed-entry hulls | pymatgen; optionally ASE/spglib where suitable. Simulated patterns do not reproduce every instrument/microstructure effect.              |
| Powder refinement/QPA                                                                        | GSAS-II, FullProf or available licensed TOPAS; preserve project files, phase models, settings, covariance and profile plots.             |
| Inorganic SC-XRD solution/refinement                                                         | Appropriate integration/scaling package, SHELX/Olex2 or Jana; preserve reflection data, correction/twin models and validation output.    |
| Laue indexing/orientation                                                                    | LaueTools or instrument software with calibrated geometry and stated reference frames.                                                   |
| Total-scattering reduction/PDF modeling                                                      | Appropriate DiffPy/PDFgetX or facility workflow; distinguish data corrections from structural model fitting.                             |
| CALPHAD equilibrium                                                                          | pycalphad or available assessed commercial workflow; requires a suitable thermodynamic database, not only a package install.             |
| EBSD orientation/grain analysis                                                              | MTEX or suitable instrument/open software; preserve reconstruction/cleanup definitions and raw-pattern access where possible.            |
| TEM/EDS/EELS processing                                                                      | Suitable microscope software or HyperSpy-based workflow when its signal model fits; preserve energy/geometry/thickness/dose calibration. |

The skill bundles scientific guidance, not the upstream programs or scripts. Use published pymatgen/pycalphad skills if available for a corresponding implementation task, but do not assume they or their relative script paths are installed here. Consult official documentation and the local package version before executing an API. Install only the dependencies needed for the user's task.

## Calculations and fitting

State input values and provenance, model, units, geometry/boundary conditions and normalization. Check composition conversion, mass/charge balance and plausible limits. Distinguish numerical convergence from adequacy of the physical model and accuracy of the input database. Preserve parameter covariance and systematic/model uncertainty where consequential. Report executed versus illustrative calculations explicitly.

Material databases contain different kinds of evidence: experimental structures/diagrams, predicted structures/energies and aggregated properties. Preserve that distinction; a Materials Project hull is not an experimental phase diagram. Keep computed entries consistent in energy/correction scheme and normalization. A retrieved structure ID needs its material state, disorder and original source checked before it can represent the specimen.

Use authenticated/commercial services only when available and appropriate; a named database does not imply access or licensing. Respect record/data terms and avoid substituting synthetic examples for real thermodynamic assessments. Keep credentials out of output and use only the requested chemical system/fields when querying external services.

Official starting points: [pymatgen](https://pymatgen.org/), [pycalphad](https://pycalphad.org/docs/latest/), [LaueTools](https://lauetools.readthedocs.io/en/latest/) and [DiffPy](https://www.diffpy.org/doc/pdfgetx/2.2.0/tutorial.html). These links are not fixed package-version requirements.
