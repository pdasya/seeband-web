"""Reproduce the SKBcal examples in Lin and Liu, Tables 1 and 2, with stdlib.

Run with Python 3.10+. Quadrature is in sqrt(x) for smooth Hall integrands.
The inference of eta from measured S applies only to an isolated Kane band.
"""

# ruff: noqa: T201
from math import exp, pi, sqrt

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


if __name__ == "__main__":
    examples = [
        ("Table 1 VB", (350, 0.43, 342.3e-6, 3.646e24), 0.9523),
        ("Table 2 CB", (300, 0.39, -47.75e-6, 2.260e24), 0.03877),
    ]
    for label, inputs, published in examples:
        result = example(*inputs, 1200, 55)
        fine = example(*inputs, 2400, 55)
        extended = example(*inputs, 2400, 70)
        eta, hall_factor, mass = extended
        print(f"{label}: eta={eta:.9f}, r_H={hall_factor:.9f}, m_DOS/m_e={mass:.8f}")
        grid_delta = max(abs(a - b) for a, b in zip(result, fine, strict=True))
        tail_delta = max(abs(a - b) for a, b in zip(fine, extended, strict=True))
        print(f"Grid change={grid_delta:.3e}; tail change={tail_delta:.3e}")
        print(f"Published {published}; relative mass difference={abs(mass / published - 1):.3e}")
        if max(grid_delta, tail_delta) > 1e-8 or abs(mass / published - 1) > 0.002:
            raise SystemExit(f"{label} check failed")
