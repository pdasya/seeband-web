"""Reproduce the SKBcal examples in Lin and Liu, Tables 1 and 2, with stdlib.

Run with Python 3.10+. Quadrature is in sqrt(x) for smooth Hall integrands.
The default preserves the historical two-row, stdlib-only replay. Run with
PYTHONPATH=packages/seeband_core/src .venv/bin/python \
    scripts/verify_skb_design_reference.py --core
for all 11 mass rows using imported math_module constants, independent P1–P3
acoustic limits, finite-epsilon K1 velocity/DOS moments vs K2–K4, and N scaling.
Only constants are imported from production: this checks proposed equations,
not a production Kane implementation. Synthetic transport fixtures use spin 2,
N identical isotropic intravalley pockets, signed q, and SI units throughout.

Source: Lin and Liu, Sci. Rep. 12, 7056 (2022), DOI
10.1038/s41598-022-09734-4; PDF pp. 2,4,11–12, Eqs. 8,10,14,23,26,
Tables 1–2 (SKBcal mass rows). Default modern constants remain historical.
The inference of eta from measured S applies only to an isolated Kane band.
"""

# ruff: noqa: T201
import argparse
from math import exp, pi, sqrt

from verify_spb_design_coefficients import occupation, simpson

KB = 1.380649e-23
E = 1.602176634e-19
HBAR = 6.62607015e-34 / (2 * pi)
ME = 9.1093837139e-31


def integral(n, m, k, eta, epsilon, intervals, tail):
    step = sqrt(max(0, eta) + tail) / intervals

    def integrand(t):
        x = t * t
        a = exp(-abs(x - eta))
        window = a / (1 + a) ** 2
        return (
            2
            * t
            * window
            * x**n
            * (x + epsilon * x**2) ** m
            * ((1 + 2 * epsilon * x) ** 2 + 2) ** (k / 2)
        )

    total = integrand(0) + integrand(intervals * step)
    for i in range(1, intervals):
        total += (4 if i % 2 else 2) * integrand(i * step)
    return step * total / 3


def example(temperature, gap_ev, signed_s, hall_density, intervals, tail):
    epsilon = KB * temperature / (gap_ev * E)
    target_s = abs(signed_s)

    def moment(n, m, k, eta):
        return integral(n, m, k, eta, epsilon, intervals, tail)

    lo, hi = -15, 15
    for _ in range(52):
        eta = (lo + hi) / 2
        seebeck = KB / E * (moment(1, 1, -2, eta) / moment(0, 1, -2, eta) - eta)
        if seebeck > target_s:
            lo = eta
        else:
            hi = eta
    eta = (lo + hi) / 2
    longitudinal = moment(0, 1, -2, eta)
    density = moment(0, 1.5, 0, eta)
    hall_factor = moment(0, 0.5, -4, eta) * density / longitudinal**2
    mass_me = (
        HBAR**2
        / (2 * KB * temperature * ME)
        * (3 * pi**2 * hall_factor * hall_density / density) ** (2 / 3)
    )
    return eta, hall_factor, mass_me


# Each tuple is T [K], gap [eV], signed S [V/K], n_H [m^-3], SKBcal m_D/m_e.
# Values transcribed from the original table images, including rounded outputs.
TABLES = [
    (
        "Table 1 VB",
        [
            (350, 0.43, 342.3e-6, 3.646e24, 0.9523),
            (400, 0.43, 354.4e-6, 4.327e24, 1.031),
            (425, 0.43, 367.3e-6, 4.894e24, 1.169),
            (525, 0.43, 395.7e-6, 14.71e24, 2.484),
            (550, 0.43, 370.7e-6, 22.28e24, 2.573),
            (600, 0.43, 366.0e-6, 33.96e24, 3.023),
        ],
    ),
    (
        "Table 2 CB",
        [
            (300, 0.39, -47.75e-6, 2.260e24, 0.03877),
            (400, 0.39, -71.77e-6, 2.252e24, 0.04488),
            (500, 0.39, -86.59e-6, 2.240e24, 0.04480),
            (600, 0.39, -103.8e-6, 2.252e24, 0.04728),
            (700, 0.39, -108.6e-6, 2.417e24, 0.04560),
        ],
    ),
]


def table_checks(all_rows=False):
    for label, rows in TABLES:
        for temperature, gap, signed_s, hall_density, published in rows if all_rows else rows[:1]:
            inputs = temperature, gap, signed_s, hall_density
            result = example(*inputs, 1200, 55)
            fine = example(*inputs, 2400, 55)
            extended = example(*inputs, 2400, 70)
            eta, hall_factor, mass = extended
            case = label
            if all_rows:
                case += f" T={temperature} K gap={gap} eV S={signed_s:.7g} V/K"
                case += f" nH={hall_density:.7g} m^-3"
            print(f"{case}: eta={eta:.9f}, r_H={hall_factor:.9f}, m_DOS/m_e={mass:.8f}")
            grid_delta = max(abs(a - b) for a, b in zip(result, fine, strict=True))
            tail_delta = max(abs(a - b) for a, b in zip(fine, extended, strict=True))
            print(f"Grid change={grid_delta:.3e}; tail change={tail_delta:.3e}")
            # Regression anchors use the imported historical core constants.
            # 1e-9 relative exceeds measured grid/tail error and is far below the
            # ~1e-6 change caused by accidentally retaining the modern kB value.
            if all_rows and temperature in (350, 300):
                expected_core = (
                    (-1.9837855013717587, 1.3600869936445175, 0.9522765632389062)
                    if temperature == 350
                    else (4.77681594357335, 1.1422377403061614, 0.038761516675358654)
                )
                assert max(relative_errors(extended, expected_core)) < 1e-9
                print("PASS fixed core-output anchor (1e-9 relative tolerance)")
            error = abs(mass / published - 1)
            print(f"Published {published}; relative mass difference={error:.3e}")
            if max(grid_delta, tail_delta) > 1e-8 or error > 0.002:
                raise SystemExit(f"{label} T={temperature} K check failed")


# Synthetic microscopic amplitudes: elastic modulus [Pa], deformation potential [J].
ELASTIC_PA, DEFORMATION_EV = 1e11, 10.0


def kane(eta, temperature, sign, mass_me, valleys, epsilon, panels=1600, tail=55):
    """K2–K4; return sigma, signed S, L, signed RH, occupancy C (SI)."""
    mass, q, thermal = mass_me * ME, -sign * E, KB * temperature
    mass_dos = valleys ** (2 / 3) * mass
    tau_pref = (
        6
        * pi
        * HBAR**4
        * ELASTIC_PA
        * valleys
        / ((2 * mass_dos * thermal) ** 1.5 * (DEFORMATION_EV * E) ** 2)
    )
    j0, j1, j2, u, v = [
        integral(n, m, k, eta, epsilon, panels, tail)
        for n, m, k in ((0, 1, -2), (1, 1, -2), (2, 1, -2), (0, 0.5, -4), (0, 1.5, 0))
    ]
    density = (2 * mass_dos * thermal) ** 1.5 / (3 * pi**2 * HBAR**3) * v
    hall_factor = u * v / j0**2
    mobility = E * tau_pref / mass * j0 / v  # K4 drift mobility, Hall factor removed.
    return (
        E * density * mobility,
        KB / q * (j1 / j0 - eta),
        (KB / E) ** 2 * (j2 / j0 - (j1 / j0) ** 2),
        hall_factor / (q * density),
        density,
    )


def velocity_dos(eta, temperature, sign, mass_me, valleys, epsilon, panels=1600, tail=55):
    """Independent energy moments: retain g(u), v(u), tau(u), m_c(u) explicitly.

    DOS includes spin 2 and N once; du cancels 1/(kBT) in -df/du.
    tau=K1; integrate in y=sqrt(u/kBT) to remove endpoint singularities.
    Scale tau by tau_pref to avoid tiny quadrature integrands.
    """
    mass, q, thermal = mass_me * ME, -sign * E, KB * temperature
    dos_pref = valleys / (2 * pi**2) * (2 * mass / HBAR**2) ** 1.5
    # N cancels in K1 at fixed single-valley mass: m_D**1.5=N*m_b**1.5.
    tau_pref = (
        6 * pi * HBAR**4 * ELASTIC_PA / ((2 * mass * thermal) ** 1.5 * (DEFORMATION_EV * E) ** 2)
    )
    upper = sqrt(max(eta, 0) + tail)

    def integrand(y, moment):
        if y == 0:
            return 0.0
        x = y * y
        z, d = x * (1 + epsilon * x), 1 + 2 * epsilon * x
        dos = dos_pref * sqrt(thermal * z) * d
        if moment == 4:
            return 2 * y * dos * thermal * occupation(x - eta)
        velocity_squared = 2 * thermal * z / (mass * d**2)
        tau_scaled = d / (sqrt(z) * (d**2 + 2))
        a = exp(-abs(x - eta))
        common = 2 * y * dos * velocity_squared / 3 * a / (1 + a) ** 2
        if moment == 3:
            return common * tau_scaled**2 / (mass * d)
        return common * tau_scaled * (x - eta) ** moment

    j0, j1, j2, hall, density = [
        simpson(lambda y, j=j: integrand(y, j), upper, panels) for j in range(5)
    ]
    sigma = q**2 * tau_pref * j0
    return (
        sigma,
        KB / q * j1 / j0,
        (KB / q) ** 2 * (j2 / j0 - (j1 / j0) ** 2),
        q**3 * tau_pref**2 * hall / sigma**2,
        density,
    )


def relative_errors(actual, expected):
    return [abs(a / b - 1) for a, b in zip(actual, expected, strict=True)]


def core_checks():
    import verify_spb_design_coefficients as spb

    # Independent P1–P3 reference uses FD integrals, not Kane moments. Align only
    # SI constants; its acoustic tau_ref is matched at T0 and u0, not by fitting sigma.
    spb.KB_J_K, spb.E_C, spb.HBAR_J_S, spb.ME_KG = KB, E, HBAR, ME
    maximum, parabolic = [0.0] * 5, [0.0] * 5
    grid_delta = tail_delta = limit = 0.0
    cases = 0
    for temperature in (150.0, 600.0):
        mass_me = 0.7
        spb.TAU_REF_S = (
            2
            * pi
            * HBAR**4
            * ELASTIC_PA
            / ((2 * mass_me * ME * KB * 300) ** 1.5 * (DEFORMATION_EV * E) ** 2)
        )
        for eta in (-8.0, 0.0, 12.0):
            for sign in (-1, 1):
                for valleys in (1, 2, 6):
                    args = eta, temperature, sign, mass_me, valleys
                    expected = spb.closed(*args, "acPh", 3200, 70)
                    exact = kane(*args, 0, 3200, 70)
                    errors = relative_errors(exact, expected)
                    assert max(errors) < 1e-8, (args, errors)
                    parabolic = [max(a, b) for a, b in zip(parabolic, errors, strict=True)]
                    # At fixed eta and mass, independently reduce alpha*kBT.
                    approach = [
                        max(relative_errors(kane(*args, eps, 3200, 70), expected))
                        for eps in (1e-4, 1e-6, 1e-8)
                    ]
                    assert approach[2] < approach[1] < approach[0], (args, approach)
                    assert approach[2] < 2e-6, (args, approach)
                    limit = max(limit, approach[2])
                    for epsilon in (0.0, 0.08, 0.4):
                        predicted = kane(*args, epsilon, 3200, 70)
                        direct = velocity_dos(*args, epsilon)
                        fine = velocity_dos(*args, epsilon, 3200)
                        extended = velocity_dos(*args, epsilon, 3200, 70)
                        err = relative_errors(predicted, extended)
                        maximum = [max(a, b) for a, b in zip(maximum, err, strict=True)]
                        grid_delta = max(grid_delta, *relative_errors(direct, fine))
                        tail_delta = max(tail_delta, *relative_errors(fine, extended))
                        assert max(err) < 1e-8, (args, epsilon, err)
                        assert sign * predicted[1] < 0 and sign * predicted[3] < 0
                        # Hold single-valley mass, eta and K1 material amplitude fixed.
                        one = kane(eta, temperature, sign, mass_me, 1, epsilon, 3200, 70)
                        scales = valleys, 1, 1, 1 / valleys, valleys
                        assert (
                            max(
                                abs(a / b / scale - 1)
                                for a, b, scale in zip(predicted, one, scales, strict=True)
                            )
                            < 1e-12
                        )
                        cases += 1
    assert max(grid_delta, tail_delta) < 1e-8, (grid_delta, tail_delta)
    print(
        f"PASS {cases} K1 velocity-DOS vs K2–K4 cases; max relative errors "
        f"[sigma,S,L,RH,C]={[f'{x:.3e}' for x in maximum]}"
    )
    print(
        f"Independent grid 1600->3200: max relative change={grid_delta:.3e}; "
        f"separate tail 55->70 kBT: max relative change={tail_delta:.3e}"
    )
    print(
        "PASS 36 epsilon=0 comparisons with independent P1–P3 acoustic FD expressions; "
        f"max relative errors [sigma,S,L,RH,C]={[f'{x:.3e}' for x in parabolic]}"
    )
    print(f"PASS epsilon=1e-4,1e-6,1e-8 approach monotonic; final max error={limit:.3e}")
    print(
        "PASS signed CB/VB S and RH; N=1,2,6 at fixed single-valley mass and eta: "
        "sigma,C scale N; RH scales 1/N; S,L,rH invariant (epsilon=0,.08,.4)."
    )
    fixture = kane(0, 300, 1, 0.7, 6, 0.08, 3200, 70)
    print(
        "Synthetic example T=300K eta=0 CB mb=.7me N=6 epsilon=.08:",
        *(f"{v:.10g}" for v in fixture),
    )
    print("Units [S/m,V/K,V^2/K^2,m^3/C,m^-3]; Cl=1e11 Pa; Edef=10 eV.")
    print("Limits: selected isotropic acoustic fixtures; no Kane production or fit validation.")


def main():
    global KB, E, HBAR, ME
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--core", action="store_true", help="use core constants; run extended checks"
    )
    args = parser.parse_args()
    if args.core:
        if not __debug__:
            parser.error("--core requires Python assertions to be enabled")
        from seeband_core import math_module as mm

        KB, E, HBAR, ME = mm.kB, mm.e, mm.hbar, mm.me
        print(f"CORE CONSTANTS from {mm.__name__}")
        print(f"kB={KB:.12e}; e={E:.12e}; hbar={HBAR:.12e}; me={ME:.12e}")
    table_checks(all_rows=args.core)
    if args.core:
        core_checks()


if __name__ == "__main__":
    main()
