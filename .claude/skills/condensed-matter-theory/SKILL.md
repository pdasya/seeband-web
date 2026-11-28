---
name: condensed-matter-theory
description: Analytic condensed matter theory for derivations and physical consistency checks. Use when deriving or reviewing electronic or spin transport, Boltzmann kinetics and relaxation times, multiband conductivity, Hall and thermoelectric coefficients, Kubo response, Wigner transport, model Hamiltonians or magnetism, or when judging whether a fit or approximation means something physically. Not for production DFT or instrument workflows.
---

# Condensed Matter Theory Skill

Build a traceable connection from a defined model to a physical observable. Keep exact identities, controlled approximations, phenomenological assumptions and numerical evidence distinguishable.

## Select the relevant reference

Read the reference for each branch actually used; do not load the entire library.

| Task                                                                                              | Read                                                                              |
| ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Construct or transform a Hamiltonian, choose a basis, identify symmetry                           | [Hamiltonians and symmetry](references/hamiltonians-and-symmetry.md)              |
| Susceptibility, conductivity, retarded/Matsubara response                                         | [Linear response and Kubo](references/linear-response-and-kubo.md)                |
| Semiclassical distributions, scattering times, multiband conductivity                             | [Boltzmann transport](references/boltzmann-transport.md)                          |
| Density-matrix kinetics, phase-space gradients, interband coherence, phonon Wigner heat transport | [Wigner transport](references/wigner-transport.md)                                |
| Exchange, magnetic order, Curie–Weiss, mean field, spin waves                                     | [Magnetism](references/magnetism.md)                                              |
| Symbolic algebra or numerical verification                                                        | [Symbolic and numerical checks](references/symbolic-and-numerical-checks.md)      |
| Physical literature or tool documentation is needed                                               | [Sources and scope](references/sources.md)                                        |
| SeeBand SPB/DPB formulas, scattering laws, μ(T), Hall or Lorenz in this repository                | the project skill `seeband-transport-physics`, which fixes the code's conventions |

## Working contract

1. **Identify the target.** Name the observable and requested level: explanation, derivation, model comparison or executable calculation. Scale the work to that request.
2. **Fix the model and conventions.** State the degrees of freedom, relevant scales, dimension, basis, ensemble and boundary conditions that affect the answer. For transport add signed charge, momentum variable, Fourier/response conventions, normalization and order of limits. Ask only when an unresolved choice changes the result; otherwise state a reasonable choice and proceed.
3. **Choose the approximation.** Identify its control parameter or physical justification. Separate gradient expansion, band projection, weak scattering and linear response: one does not establish the others. State when no controlled error estimate exists.
4. **Derive the observable.** Connect it to the Hamiltonian or source coupling. Preserve operator order, degeneracies, integration measures and required contact terms. Explain consequential steps; use symbolic tools for burdensome algebra when useful.
5. **Check the result.** Check dimensions/normalization, relevant symmetry and an appropriate solvable limit. Add an independent matrix or numerical check when it resolves a real uncertainty. Report checks actually performed separately from checks proposed.
6. **Deliver the physics.** Lead with the result and its validity regime, then the necessary derivation, verification and unresolved limitations. Respond in the user's language. Cite verified sources for literature-dependent claims; never invent equation numbers or claim a reference was read when only its abstract was available.

## Frequent failure modes

- Small gradients do not by themselves justify discarding Wigner coherences; projection needs a separate argument.
- A broadened finite-system spectrum does not establish a bulk dissipative DC coefficient.
- A fitted curve or a converged solver does not validate a microscopic mechanism.
- A mean-field instability is an approximation result, not proof of a transition.
- A scalar CAS symbol does not implement a noncommuting operator.

## Working in this repository

- Prefer a run over a reading. When Bash is available, evaluate the formula at the limit or with an independent quadrature, and label each claim **ran it** or **read it**.
- Put scratch scripts outside the repository, or in the scratchpad, and never in tracked files.
- Measurements stay private: do not paste raw user data into external tools or services.
- Agent review never replaces the physicist who confirms a change.

No library, API key or companion skill is mandatory. Use available tools and verify version-sensitive APIs before execution. Production DFT/DMFT/DMRG/QMC, CALPHAD and MPMS/PPMS ingestion require additional task-specific workflows; do not imply they are implemented here.
