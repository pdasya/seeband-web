# SPB Hall fit correction (P4/P12)

SPB S + ρ + R_H is enabled after fixing both #83 and its prerequisite #103.
This changes numerical results in the unreleased Physics fixes stage. Human
physicist confirmation, desktop parity (#71), and author review (#80) remain
pending. Agent review does not satisfy those requirements.

## Statistics and signs

The Hall integrals use the chemical potential μ(T) that conserves the carrier
density defined by E_F at zero temperature. The old expression used E_F at
every temperature. With unnormalised Fermi integrals and acoustic scattering,

`R_H n e = -sign(m) (3/4) F_{-1/2}(x) F_{1/2}(x) / F_0(x)^2`,

where `x = sign(m) μ(T) / T`, `n` is in m⁻³, and `e` is positive. The magnitude
approaches 1 in the degenerate limit and 3π/8 in the nondegenerate limit.
Positive mass represents electrons and negative mass represents holes.

## Fit and control scales

- The Hall amplitude is `E = -sign(m) |m|^(3/2)`, with physical mass in mₑ.
  Its inverse is `m = -sign(E) |E|^(2/3)`.
- The transform decreases with mass, so transformed bounds reverse order.
  A fit preserves the carrier branch selected by its nonzero initial mass.
- SPB Hall mass controls divide their integer value by 100, consistently
  with the other SPB modes. Default physical fit bounds are −3 to +3 mₑ.
- Mixed-scattering C is a dimensionless ratio at 300 K. The resistivity
  solver uses `300 C` in kelvin, then divides its returned value and standard
  error by 300.
- The desktop's nonexistent slider and short resistivity argument slice
  are GUI defects; the registry adapter passes the complete parameter list.

The desktop mode table retains its original scales, with explicit web
overrides for the repaired mass scale and bounds. Historical desktop golden
captures remain evidence of the original implementation. New synthetic
expectations and recovery tests validate the corrected mode without claiming
a working desktop reference for it.

## Validation and remaining limits

The physical tests compare against independent SciPy quadrature and a
constant-density root, exercise both Hall signs and the two limiting factors,
and recover known synthetic parameters for all three scattering mechanisms.
Synthetic data are model-generated inputs, not measurements.

A local check on Python 3.13.18, NumPy 2.5.4 and SciPy 1.18.1 also fitted the
three recorded example measurement sets using SPB Seebeck initial estimates
and all three scattering mechanisms. All nine fits converged and produced
finite redraws. The fitted masses were positive for `01_Fe2VAl09Si01` and
`02_SiP`, and negative for `03_AWI32_SI`. The first example reached the upper
mass bound of 3 mₑ: convergence alone does not establish physical validity.

The existing no-carrier chemical-potential issue (#106) remains flagged when
`m E_F <= 0`. The existing solver and Fermi-integral underflow limitations
are not resolved by this correction. The Hall expression here assumes the
core's default scattering exponent λ = 0.
