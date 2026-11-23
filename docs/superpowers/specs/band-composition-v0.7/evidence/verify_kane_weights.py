"""Check mixed S-only coordinates against positive dimensional acoustic prefactors."""

from itertools import product
from math import exp, fsum, isclose, log1p, pi

from verify_skb_design_reference import DEFORMATION_EV, ELASTIC_PA, HBAR, KB, ME, E, integral, kane
from verify_spb_design_coefficients import fd


def weighted_s(conductivities, band_s):
    return fsum(c * s for c, s in zip(conductivities, band_s, strict=True)) / fsum(conductivities)


def compare(count, kane_index, temperature, direction, alpha):
    reference, prefactors, shapes, band_s = [], [], [], []
    for i in range(count):
        # All channels share one chemical potential; edges and masses are fixed.
        sign = direction * (-1) ** i
        eta = sign * (0.01 - (0, 0.02, -0.12)[i]) / (KB * temperature / E)
        if i == kane_index:
            mass, valleys = 0.41 + i / 4, 2 + i
            epsilon = alpha * KB * temperature / E
            sigma, thermopower, *_ = kane(eta, temperature, sign, mass, valleys, epsilon)
            prefactor = (
                2
                * E**2
                * HBAR
                * valleys
                * ELASTIC_PA
                / (pi * mass * ME * (DEFORMATION_EV * E) ** 2)
            )
            shape = integral(0, 1, -2, eta, epsilon, 1600, 55)
            if alpha == 0:
                assert isclose(shape, log1p(exp(eta)) / 3, rel_tol=1e-9)
        else:
            prefactor = (i + 1) * 27_000
            shape = log1p(exp(eta))
            sigma = prefactor * shape
            thermopower = KB / (-sign * E) * (2 * fd(1, eta) / shape - eta)
        assert isclose(prefactor * shape, sigma, rel_tol=1e-10)
        reference.append(sigma)
        prefactors.append(prefactor)
        shapes.append(shape)
        band_s.append(thermopower)
    target = weighted_s(reference, band_s)
    # z_1=1 and n-1 controls after removal of the common dimensional scale.
    weights = [b / prefactors[0] for b in prefactors]
    reduced = weighted_s([z * g for z, g in zip(weights, shapes, strict=True)], band_s)
    for factor in (1e-4, 1e4):
        assert abs(weighted_s([factor * v for v in reference], band_s) - reduced) < 1e-14
    if count > 1:
        weights[-1] *= 4
        changed = weighted_s([z * g for z, g in zip(weights, shapes, strict=True)], band_s)
        assert abs(changed - reduced) > 1e-12
        weights[-1] = 0
        inactive = weighted_s([z * g for z, g in zip(weights, shapes, strict=True)], band_s)
        assert abs(inactive - weighted_s(reference[:-1], band_s[:-1])) < 1e-14
    assert abs(target - reduced) < 1e-14  # V/K, also valid at compensation.


cases = 0
for count in (1, 2, 3):
    for index, temperature, sign, alpha in product(range(count), (100, 300, 800), (-1, 1), (0, 2)):
        compare(count, index, temperature, sign, alpha)
        cases += 1
print(f"{cases} comparisons passed: dimensional and relative S agree within 1e-14 V/K.")  # noqa: T201
print("Tested both overall scalings, changed and zero nonreference weights, N > 1 and J0 -> F0/3.")  # noqa: T201
