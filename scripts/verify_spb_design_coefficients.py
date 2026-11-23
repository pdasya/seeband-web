#!/usr/bin/env python3
"""Independent synthetic SPB coefficient evidence; no production imports.

Run: python scripts/verify_spb_design_coefficients.py (standard library only).
3D isotropic unbounded parabola, mass in kg, spin 2, N valleys excluding spin.
q=-s*e, s=+1 CB/-1 VB; eta=s*(mu-edge)/(kB*T), u>=0 in joules.
F_j(eta)=integral_0^infinity x^j/(1+exp(x-eta)) dx, unnormalized.
tau=tau_ref*(T/300K)^t*(u/(kB*300K))^(lambda-1/2).
acPh=(lambda,t)=(0,-1), alloy/dis=(0,0), ionized=(2,0): synthetic
power laws, not microscopic amplitudes or fits. No Kane or screened Coulomb.
Closed FD expressions are compared with direct radial k-space transport
moments and the weak-field Hall integral (v=hbar*k/m, cyclotron mass=m).
S [V/K], L [W ohm/K^2], sigma [S/m], R_H [m^3/C], n [m^-3].
S=K1/(q*T*K0); L=(K2/K0-(K1/K0)^2)/(q*T)^2; sigma=q^2*K0.
H=q^3/3 * integral v^2*tau^2/m*(-df/du)*2N d^3k/(2pi)^3;
R_H=H/sigma^2. SI dimensions: H=[sigma]*[q*tau/m]=sigma/Tesla,
so R_H=[1/(sigma*Tesla)]=m^3/C. The dimensionless Hall factor is q*n*R_H.
"""

# ruff: noqa: T201 -- standalone evidence reports deterministic results to stdout.

import math
import platform

from verify_band_composition_design import require_valley_count

E_C = 1.602176634e-19
KB_J_K = 1.380649e-23
HBAR_J_S = 1.054571817e-34
ME_KG = 9.1093837139e-31
TAU_REF_S = 1e-14
LAWS = {"acPh": (0, -1), "alloy/dis": (0, 0), "ionized": (2, 0)}


def simpson(function, upper, panels):
    return (
        upper
        / (3 * panels)
        * math.fsum(
            (1 if j in (0, panels) else 4 if j % 2 else 2) * function(upper * j / panels)
            for j in range(panels + 1)
        )
    )


def occupation(z):
    t = math.exp(-abs(z))
    return t / (1 + t) if z >= 0 else 1 / (1 + t)


def fd(order, eta, panels=1600, tail=50.0):
    # x=y^2 resolves the integrable x^-1/2 singularity of F_-1/2.
    return simpson(
        lambda y: 2 * y ** (2 * order + 1) * occupation(y * y - eta),
        math.sqrt(max(eta, 0.0) + tail),
        panels,
    )


def closed(eta, temperature_k, sign, mass_me, valleys, law, panels=1600, tail=50.0):
    require_valley_count(valleys)
    lam, t = LAWS[law]
    mass, q = mass_me * ME_KG, -sign * E_C
    thermal = KB_J_K * temperature_k
    c = valleys / (2 * math.pi**2) * (2 * mass / HBAR_J_S**2) ** 1.5
    tau = TAU_REF_S * (temperature_k / 300) ** (t + lam - 0.5)
    f = [fd(lam + j, eta, panels, tail) for j in range(3)]
    denominator = (lam + 1) * f[0]
    mean = (lam + 2) * f[1] / denominator
    sigma = q * q * 2 * c / (3 * mass) * thermal**1.5 * tau * denominator
    seebeck = KB_J_K / q * (mean - eta)
    lorenz = (KB_J_K / q) ** 2 * ((lam + 3) * f[2] / denominator - mean**2)
    hall = (
        3
        / (2 * q * c * thermal**1.5)
        * (2 * lam + 0.5)
        * (fd(2 * lam - 0.5, eta, panels, tail) / denominator**2)
    )
    density = c * thermal**1.5 * fd(0.5, eta, panels, tail)
    return sigma, seebeck, lorenz, hall, density


def momentum(eta, temperature_k, sign, mass_me, valleys, law, panels=1600, tail=50.0):
    """Direct k-space formulation; no FD integral or integration by parts."""
    require_valley_count(valleys)
    lam, t = LAWS[law]
    mass, q = mass_me * ME_KG, -sign * E_C
    thermal = KB_J_K * temperature_k
    kscale = math.sqrt(2 * mass * thermal) / HBAR_J_S
    measure = valleys * kscale**3 / math.pi**2
    upper = math.sqrt(max(eta, 0.0) + tail)

    def integrand(y, moment):
        if y == 0:
            return 0.0  # Complete radial integrands vanish even for tau~1/k.
        u = thermal * y * y
        tau = TAU_REF_S * (temperature_k / 300) ** t * (u / (KB_J_K * 300)) ** (lam - 0.5)
        velocity = HBAR_J_S * kscale * y / mass
        exp_tail = math.exp(-abs(y * y - eta))
        window = exp_tail / (1 + exp_tail) ** 2 / thermal
        common = y * y * velocity**2 / 3 * window
        if moment == 3:
            return common * tau * tau / mass
        return common * tau * (u - eta * thermal) ** moment

    k0, k1, k2, hall_integral = [
        measure * simpson(lambda y, j=j: integrand(y, j), upper, panels) for j in range(4)
    ]
    density = measure * simpson(lambda y: y * y * occupation(y * y - eta), upper, panels)
    sigma = q * q * k0
    return (
        sigma,
        k1 / (q * temperature_k * k0),
        (k2 / k0 - (k1 / k0) ** 2) / (q * temperature_k) ** 2,
        q**3 * hall_integral / sigma**2,
        density,
    )


def main():
    print(f"SYNTHETIC SPB COEFFICIENT EVIDENCE; Python {platform.python_version()}; stdlib only")
    maximum = [0.0] * 5
    grid = tail_delta = 0.0
    cases = 0
    for law in LAWS:
        for eta in (-8.0, 0.0, 12.0):
            for temperature in (150.0, 600.0):
                for sign in (-1, 1):
                    expected = closed(eta, temperature, sign, 0.7, 3, law)
                    actual = momentum(eta, temperature, sign, 0.7, 3, law)
                    refined = momentum(eta, temperature, sign, 0.7, 3, law, 3200)
                    extended = momentum(eta, temperature, sign, 0.7, 3, law, 3200, 60.0)
                    for j, (a, b, c, d) in enumerate(
                        zip(expected, actual, refined, extended, strict=True)
                    ):
                        maximum[j] = max(maximum[j], abs(a / b - 1))
                        grid = max(grid, abs(b / c - 1))
                        tail_delta = max(tail_delta, abs(c / d - 1))
                    assert actual[0] > 0 and actual[2] > 0
                    assert sign * actual[1] < 0 and sign * actual[3] < 0
                    cases += 1
        example = closed(0.0, 300.0, 1, 0.7, 3, law)
        sigma, seebeck, lorenz, hall, density = example
        factor = -E_C * density * hall
        print(
            f"{law}: eta=0 T=300K CB m=0.7me N=3: sigma={sigma:.9e} S/m; "
            f"S={seebeck:.9e} V/K; L={lorenz:.9e}; RH={hall:.9e} m^3/C; "
            f"n={density:.9e} m^-3; q*n*RH={factor:.9f}"
        )
        n1 = closed(0.0, 300.0, 1, 0.7, 1, law)
        reflected = closed(0.0, 300.0, -1, 0.7, 3, law)
        mass4 = closed(0.0, 300.0, 1, 2.8, 3, law)
        assert abs(sigma / n1[0] - 3) < 1e-12 and abs(hall / n1[3] - 1 / 3) < 1e-12
        assert all(
            abs(reflected[j] / example[j] - (-1 if j in (1, 3) else 1)) < 1e-12 for j in range(5)
        )
        assert abs(mass4[0] / sigma - 2) < 1e-12 and abs(mass4[3] / hall - 1 / 8) < 1e-12
        low, high = [closed(0.0, t, 1, 0.7, 3, law)[0] for t in (150.0, 600.0)]
        exponent = LAWS[law][0] + 1 + LAWS[law][1]
        assert abs(high / low / 4**exponent - 1) < 1e-12
        mb = closed(-20.0, 300.0, 1, 0.7, 3, law)
        mb_expected = 3 * math.pi / 8 if LAWS[law][0] == 0 else 315 * math.pi / 512
        mb_error = abs((-E_C * mb[4] * mb[3]) / mb_expected - 1)
        assert mb_error < 2e-9
        print(
            f"  PASS: CB/VB reflection; N x3 => sigma x3, RH /3; mass x4 => "
            f"sigma x2, RH /8; fixed-eta sigma~T^{exponent}; "
            f"Boltzmann rH={mb_expected:.9f}, relative error={mb_error:.3e}"
        )
    assert max(maximum) < 1e-8 and grid < 1e-9 and tail_delta < 1e-9
    print(
        f"PASS {cases} independent comparisons; max relative errors "
        f"[sigma,S,L,RH,n]={[f'{x:.3e}' for x in maximum]}; "
        f"1600->3200 grid={grid:.3e}; separate 50->60 kBT tail={tail_delta:.3e}"
    )
    print(
        "Limits: selected synthetic parabolic fixtures, weak field, isotropic scalar tau; "
        "no production regression, Kane law, fitting or physicist approval asserted."
    )


if __name__ == "__main__":
    main()
