# Published foundations and source use

## Adapted published skills

This is a synthesis and specialization of published skills, with added guidance for inorganic solids. The original profile prose and scripts are not loaded as dependencies. The development workspace retains source snapshots and their hashes separately from the installed skill.

### K-Dense scientific-agents

Repository: [K-Dense-AI/scientific-agents](https://github.com/K-Dense-AI/scientific-agents), immutable commit `98c7fae46648724e1a43a1f2b207b0c82fcc462e`, retrieved 2026-11-14. The following are published SKILL.md files, not merely role names:

- [materials-scientist](https://github.com/K-Dense-AI/scientific-agents/blob/98c7fae46648724e1a43a1f2b207b0c82fcc462e/scientific-agents/materials-scientist/skills/materials-scientist/SKILL.md): processing–structure–property reasoning; equilibrium versus solidification; Rietveld, EBSD and TEM artifact checks.
- [materials-chemist](https://github.com/K-Dense-AI/scientific-agents/blob/98c7fae46648724e1a43a1f2b207b0c82fcc462e/scientific-agents/materials-chemist/skills/materials-chemist/SKILL.md): inorganic synthesis, precursor/atmosphere history, bulk versus surface chemistry and chemical validation.
- [crystal-growth-specialist](https://github.com/K-Dense-AI/scientific-agents/blob/98c7fae46648724e1a43a1f2b207b0c82fcc462e/scientific-agents/crystal-growth-specialist/skills/crystal-growth-specialist/SKILL.md): route selection, interface/segregation, container chemistry, post-growth history and spatial quality mapping.
- [crystallographer](https://github.com/K-Dense-AI/scientific-agents/blob/98c7fae46648724e1a43a1f2b207b0c82fcc462e/scientific-agents/crystallographer/skills/crystallographer/SKILL.md): data-to-model crystallography, symmetry/twinning, refinement/validation and reflection-data provenance; only inorganic-relevant portions adapted.
- [materials-physicist](https://github.com/K-Dense-AI/scientific-agents/blob/98c7fae46648724e1a43a1f2b207b0c82fcc462e/scientific-agents/materials-physicist/skills/materials-physicist/SKILL.md): connect structural/defect state to functional observables; reconcile local and bulk sensitivity.
- [physical-chemist](https://github.com/K-Dense-AI/scientific-agents/blob/98c7fae46648724e1a43a1f2b207b0c82fcc462e/scientific-agents/physical-chemist/skills/physical-chemist/SKILL.md): distinguish thermodynamics, kinetics, instrument response and uncertainty.

MIT, Copyright (c) 2026 K-Dense, Inc.; full notice in [LICENSE.md](../LICENSE.md).

### K-Dense scientific-agent-skills

Repository: [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills), local published snapshot at commit `2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5`, retrieved 2026-11-14:

- [pymatgen](https://github.com/K-Dense-AI/scientific-agent-skills/tree/2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5/skills/pymatgen): coordinate/occupancy/parse-warning checks, tolerance-dependent symmetry, compatible computed hulls and data provenance.
- [pycalphad](https://github.com/K-Dense-AI/scientific-agent-skills/tree/2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5/skills/pycalphad): assessed database/phase/condition contract, fraction basis, mass-balance and sampling checks, equilibrium limitations.

MIT, Copyright (c) 2025 K-Dense Inc.; full notice in [LICENSE.md](../LICENSE.md). No upstream executable scripts, demo databases or pinned Python environments are bundled here.

## Adaptation decisions

Excluded polymer, soft-matter, protein/ligand crystallography and unrelated device/production workflows. Replaced universal numerical defaults, specimen quotas and method-count requirements with question- and model-dependent choices. Upstream profiles are workflow references, not authorities for every scientific statement. In particular, do not transfer blanket kV prescriptions, impurity detection thresholds, absolute stoichiometry claims, an unconditional fluorescence-filter remedy or protein validation metrics to inorganic experiments.

Added explicit atomic-PDF versus Powder Diffraction File terminology, Laue metric/energy constraints, local versus average symmetry, diffusion coefficient/frame distinctions, peritectic route selection and a cross-method worked example. These additions are authored guidance, not claimed verbatim upstream capabilities.

## Primary scientific and software sources

Use these for the relevant branch; verify material-specific claims against original studies and actual measurement conditions:

- McCusker et al., [Rietveld refinement guidelines](https://journals.iucr.org/j/issues/1999/01/00/gl0561/), J. Appl. Cryst. 32, 36–50 (1999), DOI 10.1107/S0021889898009856: profile refinement, data/model quality and uncertainty.
- [DiffPy total-scattering tutorial](https://www.diffpy.org/doc/pdfgetx/2.2.0/tutorial.html): reduction, F(Q)/G(r), processing parameters; does not replace an experiment-specific correction model.
- [LaueTools documentation](https://lauetools.readthedocs.io/en/latest/): white-beam indexing, geometry and analysis capabilities.
- Newbury and Ritchie, [Electron-excited X-ray microanalysis by EDS at 50](https://www.nist.gov/publications/electron-excited-x-ray-microanalysis-energy-dispersive-spectrometry-50-analytical), Microscopy and Microanalysis (2019), DOI 10.1017/S143192761901482X: quantitative EDS and analytical limits.
- [MTEX grain reconstruction](https://mtex-toolbox.github.io/EBSD.calcGrains.html): analysis definitions and configurable grain reconstruction.
- [Cambridge Kirkendall overview](https://www.phase-trans.msm.cam.ac.uk/kirkendall.html): lattice-marker motion and diffusion mechanisms.
- [pymatgen](https://pymatgen.org/) and [pycalphad](https://pycalphad.org/docs/latest/): official tool contracts; development/latest documentation can differ from an installed release.

For material-specific growth temperatures, phase diagrams, transport constants or container compatibility, obtain the applicable primary paper/assessment and match composition, pressure/atmosphere and thermal history. Give traceable citations and distinguish measured values, model results and proposed tests. If only an abstract is accessible, state that access limit instead of implying the full method was inspected.
