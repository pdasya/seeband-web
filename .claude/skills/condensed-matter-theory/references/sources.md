# Sources, attribution and coverage

Links checked on 2026-11-14. Treat these as starting points, not as a claim that every result in them has been reproduced. Equation conventions in this skill are declared locally and may differ from a reference. Read the relevant original sections before borrowing a quantitative result or equation number.

## Physical sources

- Christian Wickles and Wolfgang Belzig, _Effective Quantum Theories for Transport in Inhomogeneous Systems with Non-trivial Band Structure_, [arXiv:1209.4933](https://arxiv.org/abs/1209.4933), [full text](https://arxiv.org/html/1209.4933v1). For Wigner/Moyal formulation, controlled band transformations, geometric corrections and kinetic variables.
- G. J. Iafrate, V. N. Sokolov and J. B. Krieger, _Quantum transport and the Wigner distribution function for Bloch electrons in spatially homogeneous electric and magnetic fields_, [Phys. Rev. B 96, 144303 (2017)](https://doi.org/10.1103/PhysRevB.96.144303), [arXiv:1708.01439](https://arxiv.org/abs/1708.01439). The cited construction is ballistic; it does not provide a universal collision closure.
- Michele Simoncelli, Nicola Marzari and Francesco Mauri, _Wigner Formulation of Thermal Transport in Solids_, [Phys. Rev. X 12, 041011 (2022)](https://doi.org/10.1103/PhysRevX.12.041011), [arXiv:2112.06897](https://arxiv.org/abs/2112.06897). For the phonon heat-transport branch and its conventions. Consult the paper for detailed κ expressions; this skill does not bundle a phonon solver.
- N. D. Mermin and H. Wagner, _Absence of Ferromagnetism or Antiferromagnetism in One- or Two-Dimensional Isotropic Heisenberg Models_, [Phys. Rev. Lett. 17, 1133 (1966)](https://doi.org/10.1103/PhysRevLett.17.1133), [erratum, 17, 1307](https://doi.org/10.1103/PhysRevLett.17.1307). Keep the theorem's assumptions when applying it.
- David Tong, [Kinetic Theory](https://davidtong.org/teaching/kinetic-theory/), particularly [Linear Response](https://davidtong.org/pdfs/teaching/kinetic-theory/kinetic4.pdf), for source/observable conventions and response theory; [Solid State Physics](https://davidtong.org/teaching/solid-state-physics/) for electronic transport and magnetism. These are author-hosted lecture notes.

## Optional tool documentation

- [SymPy quantum mechanics](https://docs.sympy.org/latest/modules/physics/quantum/index.html) and [assumptions](https://docs.sympy.org/latest/guides/assumptions.html).
- [SciPy documentation](https://docs.scipy.org/doc/scipy/) for linear algebra, integration and optimization.
- [QuTiP documentation](https://qutip.readthedocs.io/) for finite-system dynamics. Check installed-version solver and unit conventions before execution.

## Prior skill collections studied

The design was informed by [K-Dense Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills/tree/2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5/skills) and [ResearchCraft](https://github.com/raktim-mondol/hermes-plugin-researchcraft/tree/4bc855e8489cd8abecd8e455470fc3d1ad139f09/skills). In particular: SymPy, uncertainty-and-units, scientific-visualization, computational-physicist, theoretical-physicist, statistical-physicist and condensed-matter-physicist. Useful design ideas were conditional reference loading, explicit model assumptions and verification of observables rather than reliance on solver success.

Instructions here are newly written; upstream source files and scripts are not bundled or required. Their role is methodological prior art, not authority for physical formulas. No external harness delegation commands, version pins, collection-specific publication requirements or blanket instrument workflows are inherited.

The first version covers analytic setup and small checks. Production electronic-structure, strongly correlated lattice, anharmonic phonon, CALPHAD and instrument-data workflows need additional task-specific methods and validation.
