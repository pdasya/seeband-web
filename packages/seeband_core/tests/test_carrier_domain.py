"""Carrier-branch limits checked at fixed partner coordinates."""

from seeband_core.carrier_domain import carrier_domain


def test_same_type_fermi_energy_requires_occupied_pocket() -> None:
    assert carrier_domain("fermi_energy", "cb_cb", "n", -100, -200, 1, 1, 1) == (
        -200,
        None,
        False,
    )
    assert carrier_domain("fermi_energy", "vb_vb", "p", -100, -200, 1, 1, 1) == (
        None,
        0,
        False,
    )


def test_mixed_gap_and_overlap_include_compensation_for_both_carriers() -> None:
    assert carrier_domain("fermi_energy", "vb_cb", "p", 0, 300, 2, 1, 8) == (None, 300, True)
    assert carrier_domain("fermi_energy", "vb_cb", "n", 0, 300, 2, 1, 8) == (0, None, True)
    # N2/N1=8 and M=2 give b/a=8; neutrality divides the overlap 8:1.
    p = carrier_domain("fermi_energy", "vb_cb", "p", 0, -180, 2, 1, 8)
    n = carrier_domain("fermi_energy", "vb_cb", "n", 0, -180, 2, 1, 8)
    assert p == (None, -160, True)
    assert n == (-160, None, True)


def test_offset_and_mass_limits_at_fixed_fermi_energy() -> None:
    import pytest

    p = carrier_domain("band_offset_k", "vb_cb", "p", -80, -180, 2, 1, 8)
    n = carrier_domain("band_offset_k", "vb_cb", "n", -80, -180, 2, 1, 8)
    assert p == (-90, None, True)
    assert n == (None, -90, True)
    p_mass = carrier_domain("mass_ratio", "vb_cb", "p", -80, -180, 2, 1, 8)
    n_mass = carrier_domain("mass_ratio", "vb_cb", "n", -80, -180, 2, 1, 8)
    assert p_mass is not None and n_mass is not None
    assert p_mass[1] == pytest.approx(0.2)
    assert n_mass[0] == pytest.approx(0.2)
    assert p_mass[2] and n_mass[2]
    assert carrier_domain("band_offset_k", "vb_cb", "p", 40, 300, 1, 1, 1) == (40, None, True)
    assert carrier_domain("band_offset_k", "vb_cb", "n", 0, 300, 1, 1, 1) is None


def test_single_pocket_and_same_type_invalid_states_have_empty_mass_range() -> None:
    from math import inf

    empty = (inf, -inf, True)
    assert carrier_domain("mass_ratio", "vb_cb", "p", 0, -200, 1, 1, 1) == empty
    assert carrier_domain("mass_ratio", "vb_cb", "n", -200, -200, 1, 1, 1) == empty
    assert carrier_domain("mass_ratio", "cb_cb", "n", -200, -200, 1, 1, 1) == empty
    assert carrier_domain("mass_ratio", "vb_vb", "p", 0, -200, 1, 1, 1) == empty
    assert carrier_domain("fermi_energy", "cb_cb", "p", 100, 200, 1, 1, 1) == empty
    assert carrier_domain("mass_ratio", "vb_cb", "p", 100, 200, 1, 1, 1) is None
    assert carrier_domain("mass_ratio", "vb_cb", "n", 0, 200, 1, 1, 1) is None


def test_same_type_offset_occupancy_is_strict_only_when_other_pocket_is_empty() -> None:
    assert carrier_domain("band_offset_k", "cb_cb", "n", 0, -200, 1, 1, 1) == (None, 0, False)
    assert carrier_domain("band_offset_k", "vb_vb", "p", 0, -200, 1, 1, 1) == (0, None, False)
    assert carrier_domain("band_offset_k", "cb_cb", "n", 100, 200, 1, 1, 1) is None
    assert carrier_domain("band_offset_k", "vb_vb", "p", -100, 200, 1, 1, 1) is None


def test_log_ratios_do_not_overflow_or_divide_by_underflowed_valley_ratio() -> None:
    from math import isfinite

    for n1, n2, mass in [(1e-300, 1e300, 1e300), (1e300, 1e-300, 1e-300)]:
        domain = carrier_domain("fermi_energy", "vb_cb", "n", -100, -200, mass, n1, n2)
        assert domain is not None and domain[0] is not None
        assert isfinite(domain[0]) and -200 <= domain[0] <= 0
        offset = carrier_domain("band_offset_k", "vb_cb", "p", -100, -200, mass, n1, n2)
        assert offset is not None and offset[0] is not None and offset[0] <= -100
        assert carrier_domain("mass_ratio", "vb_cb", "p", -100, -200, mass, n1, n2)


def test_domains_agree_with_independent_zero_temperature_populations() -> None:
    from itertools import product
    from math import isclose

    from seeband_core.explicit_transport import density_settings
    from seeband_core.math_module import NoFiniteChemicalPotentialError
    from seeband_core.model_interface import BandConfiguration, CarrierType, ExplicitBands

    configurations: tuple[BandConfiguration, ...] = ("vb_cb", "cb_cb", "vb_vb")
    carriers: tuple[CarrierType, ...] = ("p", "n")
    for configuration, carrier, offset, mass, valleys, name in product(
        configurations,
        carriers,
        (-300.0, 300.0),
        (0.1, 1.0, 10.0),
        ((1.0, 1.0), (1.0, 8.0), (16.0, 2.0)),
        ("fermi_energy", "band_offset_k", "mass_ratio"),
    ):
        n1, n2 = valleys
        domain = carrier_domain(name, configuration, carrier, -100, offset, mass, n1, n2)
        candidates = (
            (0.01, 0.1, 0.2, 1.0, 4.0, 100.0)
            if name == "mass_ratio"
            else (-500.0, -300.0, -200.0, -100.0, 0.0, 100.0, 300.0, 500.0)
        )
        for value, absolute_mass in product(candidates, (1e-6, 1e6)):
            parameters = {
                "fermi_energy": -100.0,
                "band_offset_k": offset,
                "mass_ratio": mass,
                "m1": absolute_mass,
            }
            parameters[name] = value
            try:
                density_settings(ExplicitBands(configuration, None, carrier), parameters, n1, n2)
                accepted = True
            except (NoFiniteChemicalPotentialError, ValueError):
                accepted = False
            allowed = True
            if domain is not None:
                lower, upper, inclusive = domain
                allowed = (lower is None or (value >= lower if inclusive else value > lower)) and (
                    upper is None or (value <= upper if inclusive else value < upper)
                )
            # The independent DOS implementation resolves compensation at its
            # floating-point precision; analytic inclusive limits can differ by a few ULPs.
            at_compensation = (
                configuration == "vb_cb"
                and domain is not None
                and domain[2]
                and any(
                    edge is not None and isclose(value, edge, rel_tol=5e-14, abs_tol=0)
                    for edge in domain[:2]
                )
            )
            assert allowed == accepted or at_compensation, (
                configuration,
                carrier,
                parameters,
                valleys,
                domain,
            )
