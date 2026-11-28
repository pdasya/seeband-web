# Phase equilibria and transformation paths

## Fix the thermodynamic problem

State elements/components, total composition and its basis (at.%, wt.%, mole fractions), temperature, pressure and open/closed constraints. For oxides and volatile solids include oxygen/other gas chemical potentials or partial pressures where relevant. A nominally sealed ampoule still has headspace, vapor species and possible container reactions.

Use the appropriate potential: Gibbs energy at fixed T/P for a closed chemical system; include reservoir chemical potentials for an open system. Equilibrium minimizes the potential subject to material and charge constraints. Distinguish stable equilibrium from calculations with phases deliberately suppressed and from experimentally retained metastability.

For an unconstrained nonreactive component count, the Gibbs phase rule is `F = C - P + 2`; fixing pressure removes one degree of freedom. Specify what is fixed and how components are counted before using it. Additional constraints and open reservoirs change the degrees of freedom.

## Reading phase diagrams

- Distinguish phase field, solvus, solidus, liquidus, miscibility gap and order/disorder line. Keep composition axes and pressure explicit.
- Tie-line endpoints are coexisting phase compositions; the bulk composition sets fractions. For a binary two-phase field with the same mole-fraction basis, `f_alpha = (x_beta - x0)/(x_beta - x_alpha)` and `f_beta = 1 - f_alpha`. Check both total fraction and reconstructed bulk composition. Mass fractions require a consistent mass basis; convert before comparing to XRD mass QPA or microscopy volume fractions.
- Ternary tie triangles use barycentric mass balance at fixed conditions. A vertical section through a ternary is not generally a true binary with tie lines lying within the section; identify actual coexisting compositions.
- A eutectic reaction on cooling is `L -> alpha + beta`; a peritectic is `L + alpha -> beta`. A compound with incongruent melting cannot automatically be grown by freezing its stoichiometric liquid.
- DSC/DTA signals, quenched phase assemblages and composition maps constrain boundaries but do not supply an entire diagram by themselves. Report uncertainty, scan direction/rate and whether equilibrium was approached.

## Thermodynamics versus kinetics

Equilibrium diagrams predict limiting phase assemblages, not nucleation times or final grain sizes. Retained phases depend on reaction pathways, diffusion, interface motion, cooling, coherency strain and defects. TTT/CCT curves are kinetic and history-dependent.

The classical Scheil approximation assumes a well-mixed liquid, negligible solid diffusion and local interfacial equilibrium. State partitioning assumptions, phase choices and limitations due to back diffusion, incomplete mixing or solute trapping. Scheil, equilibrium and finite-diffusion predictions answer different questions.

## CALPHAD and computed hulls

Adapt the published pycalphad discipline: record TDB source/license/version/hash, assessment validity, elements, phases/sublattice models, conditions and deliberate phase exclusions. Include vacancies where the model requires them without counting them as an independent bulk elemental mole fraction. Account for coupled order/disorder definitions.

Inspect phase compositions and fractions, including multiple composition sets of one phase in a miscibility gap. Check material balance, fraction sums, finite energies and stability to increased sampling/refined temperature/composition grids. Sampling convergence alone does not establish the global minimum or the experimental accuracy of an assessment. A Gibbs-energy database does not supply diffusional mobilities automatically.

Pymatgen convex hulls built from compatible computed entries are usually static-energy stability models under their declared conditions. They are not automatically finite-temperature liquidus/solidus diagrams. Preserve competing phases, energy normalization, functional/correction compatibility and any missing entropy, pressure or gas-reservoir contributions. An on-hull structure is not a successful synthesis prediction.

## Deliverable

For a phase-diagram answer provide the system and conditions, source/data status, stable or constrained/metastable phase fields, basis of each fraction and the consequence for the requested process. Identify the next experiment or missing assessment that most changes the decision. For executable work use [data/tools](data-and-tools.md) and [official pycalphad documentation](https://pycalphad.org/docs/latest/).
