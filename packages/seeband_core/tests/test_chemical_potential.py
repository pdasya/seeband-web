"""Physical contracts for checked, deterministic chemical-potential solves."""

import numpy as np
import pytest
from seeband_core import math_module as mm


def test_dpb_zero_net_density_conserves_signed_density():
    temperatures = np.array([1.0, 100.0, 300.0, 1000.0])
    roots = mm.dpb_chemPot_vs_temp(temperatures, 1000.0, 1.01, 0.0, 1.0)
    for temp, mu in zip(temperatures, roots, strict=True):
        holes = mm.spb_carCon(mu, -1, temp)
        electrons = mm.spb_carCon(mu - 1000.0, 1.01, temp)
        assert abs(electrons - holes) / (electrons + holes) <= 1e-12


def test_spb_unsorted_temperatures_match_independent_solves():
    temperatures = np.array([1000.0, 2.0, 300.0, 2.0, 50.0])
    roots = mm.spb_chemPot_vs_temp(temperatures, 1.0, 100.0)
    independent = [mm.spb_chemPot_vs_temp(np.array([t]), 1.0, 100.0)[0] for t in temperatures]
    np.testing.assert_allclose(roots, independent, rtol=0, atol=1e-9)


@pytest.mark.parametrize("mass,energy", [(1.0, 0.0), (1.0, -10.0), (-1.0, 10.0), (0.0, 10.0)])
def test_spb_rejects_no_finite_root(mass, energy):
    with pytest.raises(ValueError):
        mm.spb_chemPot_vs_temp(np.array([300.0]), mass, energy)


@pytest.mark.parametrize("temperature", [0.0, -1.0, np.nan, np.inf])
def test_temperature_must_be_positive_and_finite(temperature):
    with pytest.raises(ValueError):
        mm.spb_chemPot_vs_temp(np.array([temperature]), 1.0, 100.0)


def test_diagnostics_certify_each_point_in_caller_order():
    temperatures = np.array([300.0, 20.0, 300.0])
    result = mm.spb_chemPot_diagnostics(temperatures, 1.0, 100.0)
    np.testing.assert_array_equal(result.status, ["converged"] * 3)
    assert np.all(result.normalized_residual <= 1e-12)
    assert result.chemical_potential[0] == result.chemical_potential[2]


def test_intrinsic_underflow_is_an_explicit_failure():
    with pytest.raises(ValueError):
        mm.dpb_chemPot_vs_temp(np.array([0.01]), 1000.0, 1.01, 0.0, 1.0)


def test_empty_temperature_arrays_are_supported():
    assert mm.spb_chemPot_vs_temp(np.array([]), 1.0, 100.0).shape == (0,)
    assert mm.dpb_chemPot_vs_temp(np.array([]), 1000.0, 1.01, 0.0, 1.0).shape == (0,)


@pytest.mark.parametrize("degen", [0.0, -1.0, np.nan, np.inf, 1e300])
def test_invalid_or_unrepresentable_degeneracy_raises_solver_error(degen):
    with pytest.raises(mm.ChemicalPotentialError):
        mm.dpb_chemPot_vs_temp(np.array([300.0]), 1000.0, 1.0, 0.0, degen)


@pytest.mark.parametrize("gap,energy", [(100.0, 100.0), (-100.0, 0.0)])
def test_two_valence_bands_reject_zero_density(gap, energy):
    with pytest.raises(mm.ChemicalPotentialError):
        mm.dpb_chemPot_vs_temp(np.array([300.0]), gap, -2.0, energy, 2.0)


@pytest.mark.parametrize("mass,energy", [(2.0, 100.0), (-2.0, -100.0)])
def test_spb_certifies_original_density_for_both_mass_signs(mass, energy):
    temperatures = np.array([20.0, 300.0, 1000.0])
    roots = mm.spb_chemPot_vs_temp(temperatures, mass, energy)
    target = mm.spb_carCon(energy, mass, 0)
    for temp, mu in zip(temperatures, roots, strict=True):
        assert abs(mm.spb_carCon(mu, mass, temp) - target) / target <= 1e-12


@pytest.mark.parametrize(
    "mass,gap,energy,degen", [(2.0, -100.0, -200.0, 3.0), (-2.0, 100.0, 50.0, 2.0)]
)
def test_dpb_certifies_original_mass_and_degeneracy_equation(mass, gap, energy, degen):
    temperatures = np.array([800.0, 50.0, 300.0, 50.0])
    result = mm.dpb_chemPot_diagnostics(temperatures, gap, mass, energy, degen)
    weighted_mass = mass * degen ** (5 / 3)
    target = -mm.spb_carCon(energy, -1, 0) + np.sign(mass) * mm.spb_carCon(
        energy - gap, weighted_mass, 0
    )
    for temp, mu in zip(temperatures, result.chemical_potential, strict=True):
        holes = mm.spb_carCon(mu, -1, temp)
        second = mm.spb_carCon(mu - gap, weighted_mass, temp)
        residual = abs(-holes + np.sign(mass) * second - target) / max(holes + second, abs(target))
        assert residual <= 1e-12
        standalone = mm.dpb_chemPot_vs_temp(np.array([temp]), gap, mass, energy, degen)[0]
        assert abs(mu - standalone) <= 1e-9


def test_error_identifies_invalid_temperature():
    with pytest.raises(mm.ChemicalPotentialError) as caught:
        mm.spb_chemPot_vs_temp(np.array([300.0, -5.0]), 1.0, 100.0)
    assert caught.value.temperature == -5.0
    assert caught.value.reason


@pytest.mark.parametrize(
    "evaluate",
    [
        lambda t: mm.spb_fermiInt_vs_temp(0, t, 1.0, 0.0),
        lambda t: mm.spb_see_vs_temp(t, 0.0, 1.0),
        lambda t: mm.spb_hall_vs_temp(t, 0.0, 1.0, 1.0),
        lambda t: mm.dpb_fermiInt_vs_temp(0, t, -1.0, 100.0, 100.0, 1.0),
        lambda t: mm.dpb_see_vs_temp(t, -1.0, 100.0, 100.0, 1.0),
    ],
)
def test_integral_and_transport_paths_reject_nonexistent_roots(evaluate):
    with pytest.raises(mm.ChemicalPotentialError):
        evaluate(np.array([300.0]))


@pytest.mark.parametrize("gap", [0.0, 1000.0, 2860.0])
def test_intrinsic_equal_bands_have_exact_gap_midpoint_potential(gap):
    temperatures = np.array([2.0, 100.0, 500.0, 2.0])
    result = mm.dpb_chemPot_diagnostics(temperatures, gap, 1.0, 0.0, 1.0)
    np.testing.assert_array_equal(result.chemical_potential, np.full_like(temperatures, gap / 2))
    assert np.all(result.normalized_residual == 0.0)


def test_finite_wrong_root_is_rejected_with_its_density_residual(monkeypatch):
    # A solver returning a finite value still has to satisfy the physical equation.
    monkeypatch.setattr(mm, "brentq", lambda *args, **kwargs: 0.0)
    with pytest.raises(mm.ChemicalPotentialError) as caught:
        mm.spb_chemPot_vs_temp(np.array([300.0]), 1.0, 100.0)
    assert caught.value.temperature == 300.0
    assert caught.value.residual is not None
    assert caught.value.residual > 1e-12


def test_iteration_failure_is_a_chemical_potential_error(monkeypatch):
    def fail_solver(*args, **kwargs):
        raise RuntimeError("iteration limit")

    monkeypatch.setattr(mm, "brentq", fail_solver)
    with pytest.raises(mm.ChemicalPotentialError) as caught:
        mm.dpb_chemPot_vs_temp(np.array([300.0]), 1000.0, 1.01, 0.0, 1.0)
    assert caught.value.temperature == 300.0
    assert isinstance(caught.value.__cause__, RuntimeError)


@pytest.mark.parametrize("energy", [-1e-6, 1e-6])
def test_dpb_root_is_continuous_through_zero_fermi_energy(energy):
    temperatures = np.array([300.0])
    intrinsic = mm.dpb_chemPot_vs_temp(temperatures, 1000.0, 1.01, 0.0, 1.0)
    nearby = mm.dpb_chemPot_vs_temp(temperatures, 1000.0, 1.01, energy, 1.0)
    # In units C*T**1.5, changing EF by -1e-6 K changes the target by at most
    # (2/3)*(1e-6/300)**1.5 < 1.3e-13; +1e-6 stays in the empty gap.
    # Around mu in [400,600] K, each reduced-band derivative exceeds 0.07:
    # F'(x) >= Gamma(3/2)*exp(-2)/(1+exp(-4/3))**2 > 0.07.
    # Thus the physical shift is < 3e-10 K. Allow 1e-8 K for table/roundoff.
    np.testing.assert_allclose(nearby, intrinsic, rtol=0, atol=1e-8)


@pytest.mark.parametrize("model", ["spb", "dpb"])
def test_roots_match_for_ascending_descending_shuffled_and_single_temperatures(model):
    def evaluate(temperatures):
        if model == "spb":
            return mm.spb_chemPot_vs_temp(temperatures, -2.0, -100.0)
        return mm.dpb_chemPot_vs_temp(temperatures, 1000.0, 1.01, 0.0, 1.0)

    temperatures = np.array([20.0, 50.0, 100.0, 300.0, 800.0])
    ascending = evaluate(temperatures)
    for order in [np.arange(5)[::-1], np.array([3, 0, 4, 1, 2])]:
        np.testing.assert_allclose(
            evaluate(temperatures[order]), ascending[order], rtol=0, atol=1e-9
        )
    singles = [evaluate(np.array([temperature]))[0] for temperature in temperatures]
    np.testing.assert_allclose(singles, ascending, rtol=0, atol=1e-9)


def test_intrinsic_balance_is_certified_before_subnormal_density_rounding():
    temperature, gap, mass = 1e-20, 1.4e-17, 1.01
    result = mm.dpb_chemPot_diagnostics(np.array([temperature]), gap, mass, 0.0, 1.0)
    # Both bands are in the Boltzmann limit. Solve the ratio n/p = 1 analytically.
    expected = (gap - 1.5 * temperature * np.log(mass)) / 2
    assert result.chemical_potential[0] == pytest.approx(expected, rel=1e-14, abs=0)
    assert result.normalized_residual[0] <= 1e-12


def test_representable_intrinsic_negative_tail_has_a_certified_root():
    result = mm.dpb_chemPot_diagnostics(np.array([2.0]), 2833.6537, 0.25845, 2192.647, 7.6606)
    assert result.chemical_potential[0] == pytest.approx(1413.7662037668432, abs=1e-9)
    assert result.normalized_residual[0] <= 1e-12


def test_spb_sommerfeld_limit_has_the_expected_temperature_shift():
    energy = 10000.0
    temperatures = np.array([1.0, 10.0, 100.0])
    roots = mm.spb_chemPot_vs_temp(temperatures, 1.0, energy)
    # For a 3D parabolic band, mu = EF - pi^2 T^2/(12 EF) + O(T^4/EF^3).
    # Budget 10*T^4/EF^3 for the omitted term and the existing high-eta approximation.
    reference = energy - np.pi**2 * temperatures**2 / (12 * energy)
    assert np.all(abs(roots - reference) <= 10 * temperatures**4 / energy**3 + 1e-9)


def test_spb_boltzmann_limit_matches_classical_density():
    energy, temperature = 1.0, 1000.0
    # n(0)/[C*T^1.5] = (2/3)*(EF/T)^1.5 and F_1/2(eta) ~ Gamma(3/2)*exp(eta).
    fugacity = (2 / 3) * (energy / temperature) ** 1.5 / (np.sqrt(np.pi) / 2)
    reference = temperature * np.log(fugacity)
    root = mm.spb_chemPot_vs_temp(np.array([temperature]), 1.0, energy)[0]
    # Classical truncation and the existing 0.27 tail correction are O(fugacity).
    assert abs(root - reference) <= temperature * fugacity


def test_intrinsic_unequal_bands_match_classical_mass_and_degeneracy_shift():
    temperatures = np.array([50.0, 100.0])
    gap, mass, degeneracy = 10000.0, 2.0, 3.0
    # Equal classical electron/hole populations, with the model's N^(5/3) mass.
    reference = gap / 2 - temperatures * (0.75 * np.log(mass) + 1.25 * np.log(degeneracy))
    roots = mm.dpb_chemPot_vs_temp(temperatures, gap, mass, 0.0, degeneracy)
    # Both fugacities < exp(-45): classical/tail error is <1e-15 K; allow roundoff.
    np.testing.assert_allclose(roots, reference, atol=1e-9, rtol=0)


@pytest.mark.parametrize("model", ["spb", "dpb"])
def test_chemical_potential_does_not_mutate_temperature_input(model):
    temperatures = np.array([300.0, 50.0, 300.0, 100.0])
    original = temperatures.copy()
    if model == "spb":
        mm.spb_chemPot_diagnostics(temperatures, 1.0, 100.0)
    else:
        mm.dpb_chemPot_diagnostics(temperatures, 1000.0, 1.01, 0.0, 1.0)
    np.testing.assert_array_equal(temperatures, original)


@pytest.mark.parametrize(
    "evaluate",
    [
        lambda: mm.spb_chemPot_vs_temp(np.array([300.0]), 1.0, 0.0),
        lambda: mm.spb_chemPot_vs_temp(np.array([300.0]), 0.0, 100.0),
        lambda: mm.dpb_chemPot_vs_temp(np.array([300.0]), 100.0, -1.0, 100.0, 1.0),
    ],
)
def test_proven_domain_errors_have_a_distinct_catchable_type(evaluate):
    with pytest.raises(mm.NoFiniteChemicalPotentialError) as caught:
        evaluate()
    assert isinstance(caught.value, mm.ChemicalPotentialError)


def test_uncertifiable_density_is_not_classified_as_a_domain_error():
    with pytest.raises(mm.ChemicalPotentialError) as caught:
        mm.dpb_chemPot_vs_temp(np.array([0.01]), 1000.0, 1.01, 0.0, 1.0)
    assert not isinstance(caught.value, mm.NoFiniteChemicalPotentialError)


@pytest.mark.parametrize(("temperature", "mass"), [(0.251, 0.362), (0.253, 0.369)])
def test_intrinsic_root_residual_is_certified_at_the_returned_potential(temperature, mass):
    import mpmath as mp

    gap = 3000.0
    result = mm.dpb_chemPot_diagnostics(np.array([temperature]), gap, mass, 0.0, 1.0)
    with mp.workdps(60):
        # The reduced potentials are below -5900, where all nonclassical terms
        # are far below the accuracy needed to certify the returned binary64 mu.
        mu = mp.mpf(float(result.chemical_potential[0]))
        log_ratio = mp.mpf("1.5") * mp.log(mp.mpf(mass)) + (2 * mu - gap) / mp.mpf(temperature)
        reference = abs(float(mp.tanh(log_ratio / 2)))
    assert reference <= 1e-12
    assert abs(result.normalized_residual[0] - reference) <= 1e-15


@pytest.mark.parametrize("reduced", [-744.0, -746.0])
def test_density_restores_the_boltzmann_factor_after_applying_dimensional_scale(reduced):
    import mpmath as mp

    temperature = 2.0
    with mp.workdps(60):
        scale = 4 * mp.pi * (2 * mm.me * mm.kB * temperature / mm.h**2) ** mp.mpf("1.5")
        reference = float(scale * mp.gamma(mp.mpf("1.5")) * mp.exp(reduced) * mp.mpf("1e-6"))
    actual = mm.spb_carCon(reduced * temperature, 1.0, temperature)
    assert actual / reference == pytest.approx(1.0, rel=1e-12)
