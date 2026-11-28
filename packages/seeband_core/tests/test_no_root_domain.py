"""P15 (#106): the analytic no-root domains, checked at and across each edge.

The T=0 carrier balance fixes the conserved density. Where it is zero for bands of one
carrier type, no finite chemical potential conserves it at T > 0. Points just inside
each edge are checked against an independent mpmath density, not the solver's residual.
"""

import mpmath as mp
import numpy as np
import pytest
from seeband_core import math_module as mm

TEMPERATURES = np.array([2.0, 50.0, 300.0, 1000.0])


def _carriers(edge_distance_k: float, temperature_k: float) -> mp.mpf:
    """Integral of sqrt(E) f(E) over one parabolic band, in K^(3/2), for an edge distance."""
    eta = mp.mpf(edge_distance_k) / temperature_k
    return -mp.gamma(1.5) * mp.polylog(1.5, -mp.exp(eta)) * mp.mpf(temperature_k) ** 1.5


def _zero_temperature(edge_distance_k: float) -> mp.mpf:
    return mp.mpf(2) / 3 * max(mp.mpf(edge_distance_k), 0) ** 1.5


def _assert_conserved(densities, target):
    for density in densities:
        assert abs(density - target) <= mp.mpf("1e-9") * target


@pytest.mark.parametrize(
    ("mass", "fermi_energy"),
    [(1.0, 0.0), (1.0, -1.0), (1.0, -1e-300), (-1.0, 0.0), (-1.0, 1.0), (-1.0, 1e-300)],
)
def test_spb_fermi_energy_at_or_outside_the_band_has_no_root(mass, fermi_energy):
    with pytest.raises(mm.NoFiniteChemicalPotentialError) as caught:
        mm.spb_chemPot_diagnostics(TEMPERATURES, mass, fermi_energy)
    assert caught.value.code == "chemical_potential_spb_fermi_energy"


@pytest.mark.parametrize("mass", [1.0, -1.0])
@pytest.mark.parametrize("distance", [1e-9, 1e-3, 1.0])
def test_spb_fermi_energy_just_inside_the_band_conserves_density(mass, distance):
    fermi_energy = np.sign(mass) * distance
    mu = mm.spb_chemPot_diagnostics(TEMPERATURES, mass, fermi_energy).chemical_potential
    with mp.workdps(40):
        densities = [
            _carriers(np.sign(mass) * root, temperature)
            for root, temperature in zip(mu, TEMPERATURES, strict=True)
        ]
        _assert_conserved(densities, _zero_temperature(distance))


@pytest.mark.parametrize("gap", [1000.0, 0.0, -500.0])
@pytest.mark.parametrize("above", [0.0, 1e-9, 1.0, 1e4])
def test_two_valence_bands_at_or_above_the_higher_edge_have_no_root(gap, above):
    fermi_energy = max(0.0, gap) + above
    with pytest.raises(mm.NoFiniteChemicalPotentialError) as caught:
        mm.dpb_chemPot_diagnostics(TEMPERATURES, gap, -1.0, fermi_energy, 1.0)
    assert caught.value.code == "chemical_potential_dpb_fermi_energy"


@pytest.mark.parametrize(("gap", "mass"), [(1000.0, -1.0), (-500.0, -1.0), (1000.0, -0.3)])
@pytest.mark.parametrize("below", [1e-6, 1.0, 100.0])
def test_two_valence_bands_just_below_the_higher_edge_conserve_density(gap, mass, below):
    fermi_energy = max(0.0, gap) - below
    mu = mm.dpb_chemPot_diagnostics(TEMPERATURES, gap, mass, fermi_energy, 1.0).chemical_potential
    weight = mp.mpf(-mass) ** 1.5
    with mp.workdps(40):
        target = _zero_temperature(-fermi_energy) + weight * _zero_temperature(gap - fermi_energy)
        densities = [
            _carriers(-root, temperature) + weight * _carriers(gap - root, temperature)
            for root, temperature in zip(mu, TEMPERATURES, strict=True)
        ]
        _assert_conserved(densities, target)


@pytest.mark.parametrize("gap", [1000.0, 0.0, -500.0])
@pytest.mark.parametrize("fermi_energy", [-1e5, -500.0, 0.0, 500.0, 1000.0, 1e5])
def test_opposite_carrier_bands_always_have_a_root(gap, fermi_energy):
    # n - p increases strictly with mu, so any conserved difference has one finite root.
    result = mm.dpb_chemPot_diagnostics(TEMPERATURES, gap, 1.0, fermi_energy, 1.0)
    assert np.isfinite(result.chemical_potential).all()


def test_a_fermi_energy_inside_a_band_too_close_to_represent_is_a_numerical_failure():
    # The root exists, but its T=0 density underflows; this is not the no-root domain.
    with pytest.raises(mm.ChemicalPotentialError) as caught:
        mm.spb_chemPot_diagnostics(TEMPERATURES, 1.0, 1e-300)
    assert not isinstance(caught.value, mm.NoFiniteChemicalPotentialError)


@pytest.mark.parametrize(
    "evaluate",
    [
        lambda: mm.spb_chemPot_diagnostics(TEMPERATURES, 0.0, 100.0),
        lambda: mm.dpb_chemPot_diagnostics(TEMPERATURES, 1000.0, 0.0, 100.0, 1.0),
    ],
)
def test_zero_mass_is_reported_before_the_fermi_energy(evaluate):
    with pytest.raises(mm.NoFiniteChemicalPotentialError) as caught:
        evaluate()
    assert caught.value.code == "chemical_potential_zero_mass"
