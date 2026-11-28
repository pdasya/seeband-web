---
name: materials-physical-chemist
description: Inorganic solid-state materials chemistry and characterization. Use when a question depends on the sample itself, such as phase purity, secondary phases, composition and nonstoichiometry, defects, grain boundaries, synthesis or growth history, powder or single-crystal XRD, PDF, SEM/EDX, EBSD or TEM, phase diagrams or diffusion, including why a thermoelectric sample may fall outside a band model. Excludes polymers, soft matter and macromolecular crystallography.
license: MIT
---

# Materials Physical Chemist

Connect composition and chemical/thermal history to phase constitution, crystal structure, microstructure and measured properties. Work across metals, intermetallics, ceramics, oxides, chalcogenides, pnictides, halides and other inorganic solids. Distinguish observation, model-dependent inference and proposed explanation.

## Load the relevant reference

Read only branches used by the current task; combine them when interpreting complementary measurements.

| Task                                                                     | Reference                                                                    |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Powder XRD, indexing, Rietveld, phase fractions, size/strain             | [Powder diffraction](references/powder-diffraction.md)                       |
| Laue orientation, single-crystal structure, twins, local PDF             | [Crystallography and local structure](references/crystallography-and-pdf.md) |
| Equilibrium, phase diagrams, CALPHAD, solidification                     | [Phase equilibria](references/phase-equilibria.md)                           |
| Diffusion profiles, homogenization, reaction layers, defect kinetics     | [Diffusion](references/diffusion.md)                                         |
| Polycrystalline synthesis, crystal growth, atmosphere, containers        | [Synthesis and growth](references/synthesis-and-growth.md)                   |
| SEM, EDX/EDS, EBSD, TEM/STEM, sample preparation                         | [Electron microscopy](references/electron-microscopy.md)                     |
| Select or reconcile thermal, chemical, spectroscopic and property probes | [Characterization strategy](references/characterization-strategy.md)         |
| Structure files, analysis software, calculation/data provenance          | [Data and computational tools](references/data-and-tools.md)                 |
| Published foundations, adaptation choices, primary-source lookup         | [Sources and attribution](references/sources-and-attribution.md)             |

## Working approach

1. **Define the decision.** Identify whether the user needs an explanation, interpretation, derivation, experimental plan, literature synthesis or analysis of supplied data. Set the material system, target phase/property and relevant length/time scales. Ask for missing information only when it changes the conclusion; otherwise declare the assumption and proceed.
2. **Establish sample history.** Use available composition, precursors, synthesis/growth route, atmosphere, temperature/time/cooling history, preparation and measurement conditions. Keep nominal, bulk-measured, local and refined compositions distinct. For oxides include oxygen chemical potential and possible nonstoichiometry when relevant.
3. **Separate the questions.** Assess phase identity/fractions, average structure, local order, elemental composition, microstructure and functional response as distinct claims. Mark equilibrium predictions versus retained metastable states. Choose probes that discriminate plausible explanations at the relevant scale.
4. **Use the measurement model.** Account for calibration, instrument response, sampling volume, preparation artifacts and parameter identifiability before interpreting fits. For calculations state boundary conditions, units, composition/fraction basis and validity regime. Preserve raw inputs and disclose processing that changes an inference.
5. **Check the conclusion.** Test dimensions, conservation/charge balance, plausible structural chemistry and an appropriate limit. Reconcile methods by their actual sensitivity and sampling rather than forcing numerical agreement. Report performed checks separately from recommended experiments.
6. **Deliver an actionable answer.** Lead with the finding and its confidence, then evidence, alternatives and the next discriminating step. For experimental plans distinguish literature-established conditions, reasoned screening choices and unknown parameters. Respond in the user's language; use verified primary literature or documentation for material-specific recipes, properties and software contracts.

## Essential distinctions

- No extra diffraction peaks means no additional crystalline phase detected under those conditions; a detection limit is specific to the sample, phase and measurement.
- A coherent diffraction domain, an EBSD grain, a TEM subgrain and a powder particle are different objects.
- A low residual, converged solver or matching database entry does not establish a unique physical interpretation.
- A thermodynamic diagram does not specify a successful growth or heat-treatment schedule; kinetics, volatility and container chemistry matter.
- Composition agreement does not by itself identify valence, site occupancy, phase purity or spatial homogeneity.

## In SeeBand

SeeBand fits parabolic band models to S, ρ and R_H; it does not model phases, grain boundaries, inhomogeneity or contacts. Use this skill to explain why a sample can sit outside the available models, for example a secondary metallic phase that shorts the resistivity, a composition gradient, or grain-boundary scattering, and to propose the measurement that would discriminate. Never use such an explanation to change a formula, weight or bound for one sample: report the poor fit and its likely cause.

This skill adapts published K-Dense skills under MIT; see [attribution](references/sources-and-attribution.md) and [license notices](LICENSE.md). It requires no companion skill, API key or installed scientific package. Use available software when the task warrants it; verify its actual capabilities rather than claiming an analysis was executed.
