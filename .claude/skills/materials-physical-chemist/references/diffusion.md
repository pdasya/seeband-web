# Diffusion, defects and reaction layers

## Identify the coefficient and frame

Distinguish tracer/self diffusion, intrinsic component diffusion relative to the lattice, chemical interdiffusion in a specified frame, grain-boundary/surface diffusion and an effective coefficient fitted to a multiphase microstructure. They are not interchangeable. Name the species, phase, direction, temperature, composition, defect state, reference frame and measured observable.

Use `J = -D grad(c)` for a scalar concentration-based Fick model with its assumptions. For anisotropic crystals use a diffusion tensor in a declared coordinate system. Chemical-potential gradients, coupled fluxes and thermodynamic factors become important in nonideal or multicomponent systems; an elemental concentration gradient alone need not predict a flux's direction. In charged solids include electrochemical driving forces, charge neutrality and coupled carriers as appropriate.

Conservation gives `dc/dt = div(D grad(c))` for a stationary medium without sources. For composition-dependent D retain D inside the divergence. Add reaction terms, moving boundaries or advection/lattice motion when the physical problem requires them.

## Choose a solvable geometry

State initial and boundary conditions before selecting an error-function profile or diffusion length. For constant scalar D in a semi-infinite solid with an initially uniform concentration c0 and fixed surface concentration cs:

`c(x,t) = cs + (c0 - cs) erf[x/(2 sqrt(D t))]`.

This does not describe a finite pellet with two interacting surfaces, a finite source, composition-dependent D or an arbitrary multiphase diffusion couple without further work. The estimate `t ~ L^2/D` gives a scale; the prefactor depends on geometry, boundary conditions and the specified homogenization criterion. Numerical predictions need those details.

For Arrhenius fitting use `D = D0 exp[-Ea/(R T)]` for molar Ea or `D = D0 exp[-Ea/(kB T)]` for per-particle Ea; T is kelvin. Report temperature interval, coefficient type, fitting weights/covariance and any mechanism, phase or defect-concentration changes. A straight line over a narrow interval does not identify the microscopic mechanism.

In oxides, vacancy/interstitial/antisite populations and dopant charge compensation can depend on temperature and oxygen activity. Use explicit defect reactions and charge/site balance when needed. An apparent activation energy may include defect formation and migration contributions; do not call it a migration barrier without justification.

## Diffusion couples and layers

For composition profiles, check terminal compositions, calibration, spatial resolution, interface origin, specimen geometry and thermal history. Use Boltzmann–Matano/Sauer–Freise or a relevant multicomponent/moving-boundary treatment only when their assumptions hold. A single multicomponent diffusion path does not generally determine a complete diffusion matrix.

Kirkendall marker motion probes unequal intrinsic fluxes/lattice motion; interdiffusion data alone do not separate the component intrinsic diffusivities. Relating tracer and chemical coefficients needs thermodynamic and correlation information and the appropriate model. See the [Cambridge Kirkendall overview](https://www.phase-trans.msm.cam.ac.uk/kirkendall.html).

For growth of a product layer, fit a stated law such as `x^2 - x0^2 = Kp (t - t0)` and test it with several times. Kp is a parabolic growth constant under that convention, not automatically an atomic D. A relation such as `x = 2 lambda sqrt(D t)` has an additional dimensionless lambda determined by boundary/composition/interface conditions.

Example: 20 micrometres after 10 h gives `x^2/t = 1.11e-14 m^2/s`. This is a dimensional layer-growth scale; it does not determine self diffusion, and one time point does not establish a parabolic law. Check incubation, initial layer thickness, all product phases, composition endpoints, molar-volume effects and interface control before inferring transport parameters. Near-line compounds may require an integrated interdiffusion coefficient.

## Microstructure and consistency checks

Grain boundaries and dislocations can produce fast transport distinct from bulk diffusion. Select a grain-boundary diffusion regime from diffusion lengths, grain size and boundary width; do not assign an effective D to bulk transport solely because the profile fits.

Check dimensional units, positivity/physical stability of the chosen transport model, total material balance, early/late-time limits, spatial/time-grid convergence for numerical work and consistency of the predicted affected depth with the experiment's resolution. Keep homogenization, interfacial reaction, grain coarsening, densification and precipitation as different kinetic processes.
