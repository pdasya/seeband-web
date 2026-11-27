"""P18 explicit-density physics checked against the independent design oracle."""

import runpy
from pathlib import Path

import numpy as np
import pytest
from seeband_core import math_module as mm
from seeband_core.band_models import DpbModel
from seeband_core.explicit_transport import (
    explicit_curves,
    explicit_diagram,
    independent_explicit_potentials,
    reuse_explicit_potentials,
    zero_temperature_density,
)
from seeband_core.model_interface import CurveRequest, ExplicitBands

REFERENCE = runpy.run_path(
    str(Path(__file__).resolve().parents[3] / "scripts/verify_p18_contract.py")
)


@pytest.mark.parametrize("offset_ev", [-3.0, 3.0])
def test_intrinsic_wide_offset_matches_independent_quadrature(offset_ev):
    band = REFERENCE["Band"]
    offset_k = offset_ev * REFERENCE["E"] / REFERENCE["KB"]
    bands = (band(-1, 0.0, 1.7, 2, 1e-14), band(1, offset_k, 0.8, 6, 1.7e-14))
    temperatures = np.array([300.0, 800.0])
    parameters = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=offset_k)
    actual = explicit_curves(
        ExplicitBands("vb_cb", 0.0),
        "dpb_s",
        parameters,
        temperatures,
        None,
        2.0,
        6.0,
        "chemical_potential",
    )
    expected = [REFERENCE["solve"](bands, 0.0, t)[0] for t in temperatures]
    np.testing.assert_allclose(actual["chemical_potential_k"], expected, atol=2e-7, rtol=0)


@pytest.mark.parametrize(
    "configuration,doping,signs",
    [
        ("vb_vb", -2e24, (-1, -1)),
        ("vb_cb", 0.0, (-1, 1)),
        ("vb_cb", -2e24, (-1, 1)),
        ("vb_cb", 2e24, (-1, 1)),
        ("cb_cb", 2e24, (1, 1)),
    ],
)
def test_absolute_density_matches_independent_roots_and_grid_order(configuration, doping, signs):
    p = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=650.0)
    settings = ExplicitBands(configuration, doping)
    band = REFERENCE["Band"]
    bands = (band(signs[0], 0.0, 1.7, 2, 1e-14), band(signs[1], 650.0, 0.8, 6, 1e-14))
    t = np.array([100.0, 300.0, 800.0])
    actual = explicit_curves(settings, "dpb_s", p, t, None, 2, 6, "chemical_potential")
    mu = actual["chemical_potential_k"]
    expected = [REFERENCE["solve"](bands, doping, ti)[0] for ti in t]
    # Current-SI oracle differs from inherited k_B by ~5.2e-7 in populations.
    np.testing.assert_allclose(mu, expected, atol=5e-4, rtol=1e-7)
    reorder = np.array([2, 0, 1, 0])
    reordered = explicit_curves(settings, "dpb_s", p, t[reorder], None, 2, 6, "chemical_potential")[
        "chemical_potential_k"
    ]
    np.testing.assert_array_equal(reordered, mu[reorder])
    carriers = explicit_curves(settings, "dpb_s", p, t, None, 2, 6, "carrier_concentration_by_band")
    values = np.asarray(list(carriers.values())) * 1e6
    residual = abs(values.sum(axis=0) - doping) / np.maximum(abs(values).sum(axis=0), abs(doping))
    assert np.max(residual) < 1e-12


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized", "acPhDis"])
def test_migrated_curves_match_legacy_transport(sign, scattering):
    p = dict(
        m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=650.0, A=1e5, B=0.8, F=2e4, G=1.2, C=0.5, D=2.0
    )
    configuration = "vb_vb" if sign < 0 else "vb_cb"
    ef = -300.0
    doping = zero_temperature_density(configuration, p, ef, 2, 6)
    settings = ExplicitBands(configuration, doping)
    old_p = {k: v for k, v in p.items() if k not in ("mass_ratio", "band_offset_k")}
    old_p |= dict(m_eff=sign * p["mass_ratio"], band_gap=p["band_offset_k"], fermi_energy=ef)
    for kind in (
        "measured",
        "seebeck_by_band",
        "electrical_conductivity_by_band",
        "thermal_conductivity",
        "lorenz_number",
    ):
        expected = (
            DpbModel()
            .calculate(CurveRequest("dpb_s_rho_rh", old_p, 100.0, 800.0, 3, scattering, kind, 2, 6))
            .curves
        )
        actual = explicit_curves(
            settings, "dpb_s_rho_rh", p, np.linspace(100, 800, 3), scattering, 2, 6, kind
        )
        assert actual.keys() == expected.keys()
        for name in expected:
            np.testing.assert_allclose(
                actual[name],
                expected[name],
                rtol=3e-5,
                atol=1e-12,
                err_msg=f"{configuration}/{scattering}/{name}",
            )


@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
def test_same_type_reflection_and_exchange_preserve_all_transport(scattering):
    t = np.array([100.0, 300.0, 800.0])
    p = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=-450.0, A=1e5, B=0.8, F=2e4, G=1.2)
    for kind in ("measured", "thermal_conductivity", "lorenz_number"):
        actual = explicit_curves(
            ExplicitBands("vb_vb", -2e24), "dpb_s_rho_rh", p, t, scattering, 2, 6, kind
        )
        reflected = explicit_curves(
            ExplicitBands("cb_cb", 2e24),
            "dpb_s_rho_rh",
            p | {"band_offset_k": 450.0},
            t,
            scattering,
            2,
            6,
            kind,
        )
        swapped = p | dict(
            m1=0.8,
            mass_ratio=1 / p["mass_ratio"],
            band_offset_k=450.0,
            A=p["A"] * 3 * p["B"] / p["mass_ratio"],
            B=1 / p["B"],
            F=p["F"] * 3 * p["G"] / p["mass_ratio"],
            G=1 / p["G"],
        )
        exchanged = explicit_curves(
            ExplicitBands("vb_vb", -2e24), "dpb_s_rho_rh", swapped, t, scattering, 6, 2, kind
        )
        for name, value in actual.items():
            sign = -1 if name in ("seebeck_v_per_k", "hall_m3_per_c") else 1
            np.testing.assert_allclose(reflected[name], value * sign, rtol=2e-11, atol=1e-18)
            exchanged_name = name
            if "_band_1_" in name:
                exchanged_name = name.replace("_band_1_", "_band_2_")
            elif "_band_2_" in name:
                exchanged_name = name.replace("_band_2_", "_band_1_")
            np.testing.assert_allclose(exchanged[exchanged_name], value, rtol=2e-11, atol=1e-18)


def test_explicit_diagram_uses_physical_single_valley_curvature_and_gap_interval():
    p = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=650.0)
    diagram = explicit_diagram(ExplicitBands("vb_cb", 0.0), p, 2, 6)
    assert len(diagram.wavevector_nm_inv) == 101 and diagram.wavevector_nm_inv[50] == 0
    for i, mass, sign, edge in ((1, 1.7, -1, 0), (2, 0.8, 1, 650)):
        expected = edge + sign * mm.hbar**2 * (diagram.wavevector_nm_inv * 1e9) ** 2 / (
            2 * mass * mm.me * mm.kB
        )
        np.testing.assert_allclose(diagram.curves[f"band_{i}_energy_k"], expected)
    assert np.all(diagram.curves["fermi_energy_lower_k"] == 0)
    assert np.all(diagram.curves["fermi_energy_upper_k"] == 650)
    assert "fermi_energy_k" not in diagram.curves


def test_intrinsic_underflow_is_numerical_failure_not_wrong_density():
    p = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=35000.0)
    with pytest.raises(mm.ChemicalPotentialError, match="precision cannot be certified") as failure:
        explicit_curves(
            ExplicitBands("vb_cb", 0), "dpb_s", p, np.array([1.0]), None, 2, 6, "chemical_potential"
        )
    assert not isinstance(failure.value, mm.NoFiniteChemicalPotentialError)


@pytest.mark.parametrize(
    "configuration,doping,signs",
    [
        ("vb_vb", -2e24, (-1, -1)),
        ("vb_cb", 2e24, (-1, 1)),
        ("cb_cb", 2e24, (1, 1)),
    ],
)
@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized", "acPhDis"])
def test_transport_matches_independent_si_relaxation_time_moments(
    configuration, doping, signs, scattering
):
    p = dict(
        m1=1.7,
        mass_ratio=0.8 / 1.7,
        band_offset_k=450.0,
        A=1e5,
        B=0.8,
        F=2e4,
        G=1.2,
        C=0.5,
        D=2.0,
    )
    settings = ExplicitBands(configuration, doping)
    band = REFERENCE["Band"]
    t = np.array([100.0, 300.0, 800.0])
    mu = explicit_curves(settings, "dpb_s_rho_rh", p, t, scattering, 2, 6, "chemical_potential")[
        "chemical_potential_k"
    ]
    actual = explicit_curves(settings, "dpb_s_rho_rh", p, t, scattering, 2, 6)
    actual |= explicit_curves(
        settings, "dpb_s_rho_rh", p, t, scattering, 2, 6, "thermal_conductivity"
    )
    law = "alloy/dis" if scattering == "dis" else "acPh" if scattering == "acPhDis" else scattering
    r, power_t = REFERENCE["LAWS"][law]
    lam = r + 0.5
    expected = []
    for temperature, potential in zip(t, mu, strict=True):
        first = band(signs[0], 0.0, 1.7, 2, 1e-14)
        amplitude = (
            p["F"] * temperature
            if scattering == "dis"
            else p["A"] * (temperature / 300) ** 3
            if scattering == "ionized"
            else p["A"]
        )
        if scattering == "acPhDis":
            amplitude *= temperature / (temperature + 300 * p["C"])
        # Calibrate the independent physical relaxation time to public amplitude,
        # using integral x^(lambda+1)(-df/dx)=(lambda+1)*F_lambda, not core values.
        physical_factor = (
            REFERENCE["E"] ** 2
            * first.dos_si
            * (REFERENCE["KB"] * temperature) ** 1.5
            * 2
            / (3 * 1.7 * REFERENCE["m_e"])
            * (lam + 1)
        )
        tau = amplitude / physical_factor / (temperature / 300) ** power_t
        relative = p["G"] if scattering == "dis" else p["B"]
        if scattering == "acPhDis":
            relative *= (temperature + 300 * p["C"]) / (temperature + 300 * p["D"])
        first = band(signs[0], 0.0, 1.7, 2, tau)
        second = band(signs[1], 450.0, 0.8, 6, tau * relative / p["mass_ratio"] ** 1.5)
        expected.append(REFERENCE["transport"]((first, second), potential, temperature, law))
    for index, name in enumerate(
        ("seebeck_v_per_k", "resistivity_ohm_m", "hall_m3_per_c", "thermal_conductivity_w_per_m_k")
    ):
        np.testing.assert_allclose(
            actual[name], np.asarray(expected)[:, index], rtol=3e-6, atol=1e-12
        )


def test_depleted_alloy_hall_matches_independent_p18_reference():
    p = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=450.0, F=2e4, G=1.2)
    actual = explicit_curves(
        ExplicitBands("cb_cb", 2e24), "dpb_s_rho_rh", p, np.array([800.0]), "dis", 2, 6
    )["hall_m3_per_c"]
    # Independent P18 oracle with inherited core constants, in m^3/C.
    np.testing.assert_allclose(actual, [-7.038039355547361e-6], rtol=1e-7, atol=0.0)


def test_seebeck_only_does_not_require_unused_resistivity_or_hall_scale():
    settings = ExplicitBands("vb_cb", 0.0)
    p = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=35000.0)
    t = np.array([23.0])
    implicit = explicit_curves(settings, "dpb_s", p, t, None, 2, 6)
    explicit = explicit_curves(settings, "dpb_s", p, t, "acPh", 2, 6)
    np.testing.assert_array_equal(implicit["seebeck_v_per_k"], explicit["seebeck_v_per_k"])
    assert np.isfinite(implicit["seebeck_v_per_k"]).all()
    with pytest.raises(mm.ChemicalPotentialError, match="not representable"):
        explicit_curves(settings, "dpb_s_rho", p, t, "acPh", 2, 6)


def test_scoped_roots_do_not_leak_outputs_or_changed_absolute_mass():
    settings = ExplicitBands("vb_cb", 2e24)
    p = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=650.0)
    t = np.array([800.0, 100.0, 300.0, 100.0])
    with reuse_explicit_potentials():
        first = explicit_curves(settings, "dpb_s", p, t, None, 2, 6, "chemical_potential")
        expected = first["chemical_potential_k"].copy()
        first["chemical_potential_k"][:] = -999
        repeated = explicit_curves(settings, "dpb_s", p, t, None, 2, 6, "chemical_potential")
        np.testing.assert_array_equal(repeated["chemical_potential_k"], expected)
        changed = explicit_curves(
            settings, "dpb_s", p | {"m1": 2.0}, t, None, 2, 6, "chemical_potential"
        )
        assert np.any(changed["chemical_potential_k"] != expected)
        with independent_explicit_potentials():
            audited = explicit_curves(settings, "dpb_s", p, t, None, 2, 6, "chemical_potential")
        np.testing.assert_array_equal(audited["chemical_potential_k"], expected)


def test_finite_thermal_curve_at_large_conductivity():
    settings = ExplicitBands("cb_cb", 2e25)
    p = {"m1": 1.2, "mass_ratio": 1.7, "band_offset_k": 140.0, "A": 1.0e308, "B": 1.0}
    t = np.array([300.0])
    small = explicit_curves(
        settings, "dpb_s_rho", p | {"A": 1.0}, t, "acPh", 2, 3, "thermal_conductivity"
    )["thermal_conductivity_w_per_m_k"]
    large = explicit_curves(settings, "dpb_s_rho", p, t, "acPh", 2, 3, "thermal_conductivity")[
        "thermal_conductivity_w_per_m_k"
    ]
    np.testing.assert_allclose(large / p["A"], small, rtol=1e-12)


def test_overlap_compensation_roundoff_allows_both_carrier_signs():
    from seeband_core.explicit_transport import density_settings

    ratio, n1, n2, offset = 1.7, 2, 3, -140.0
    neutral = offset / (1 + (n1 / n2) ** (2 / 3) / ratio)
    p = dict(m1=1.2, mass_ratio=ratio, band_offset_k=offset, fermi_energy=neutral)
    for carrier in ("p", "n"):
        settings = ExplicitBands("vb_cb", carrier_type=carrier)
        assert density_settings(settings, p, n1, n2).net_electron_density_per_m3 == 0.0
        sign = 1 if carrier == "n" else -1
        doped = p | {"fermi_energy": neutral + sign * 1e-8}
        assert sign * density_settings(settings, doped, n1, n2).net_electron_density_per_m3 > 0
        with pytest.raises(mm.NoFiniteChemicalPotentialError):
            density_settings(settings, p | {"fermi_energy": neutral - sign * 1e-8}, n1, n2)


def test_ef_diagram_draws_only_supplied_fermi_line_and_ignores_carrier_selection():
    p = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=650.0, fermi_energy=200)
    for carrier in ("p", "n"):
        diagram = explicit_diagram(ExplicitBands("vb_cb", carrier_type=carrier), p, 2, 6)
        assert set(diagram.curves["fermi_energy_k"]) == {200}
        assert "fermi_energy_lower_k" not in diagram.curves
        assert "fermi_energy_upper_k" not in diagram.curves


@pytest.mark.parametrize(
    "configuration,density", [("vb_vb", -2e24), ("cb_cb", 2e24), ("vb_cb", 2e24)]
)
def test_density_diagram_still_inverts_fixed_density(configuration, density):
    p = dict(m1=1.7, mass_ratio=0.8 / 1.7, band_offset_k=650.0)
    diagram = explicit_diagram(ExplicitBands(configuration, density), p, 2, 6)
    ef = diagram.curves["fermi_energy_k"][0]
    assert zero_temperature_density(configuration, p, ef, 2, 6) == pytest.approx(density, rel=1e-12)


@pytest.mark.parametrize("ef", [float("inf"), float("nan"), 1e308])
def test_ef_diagram_rejects_nonfinite_or_unrepresentable_geometry(ef):
    p = dict(m1=1.0, mass_ratio=1.0, band_offset_k=1000.0, fermi_energy=ef)
    with pytest.raises(ValueError):
        explicit_diagram(ExplicitBands("cb_cb", carrier_type="n"), p, 1, 1)


def test_unsigned_fermi_contract_crosses_compensation_and_draws_one_ef_line():
    p = dict(m1=1.0, mass_ratio=1.0, band_offset_k=-100.0, fermi_energy=-80.0)
    settings = ExplicitBands("vb_cb")
    t = np.array([300.0])
    holes = explicit_curves(settings, "dpb_s", p, t, "acPh", 1, 1, "chemical_potential")
    electrons = explicit_curves(
        settings,
        "dpb_s",
        p | {"fermi_energy": -20.0},
        t,
        "acPh",
        1,
        1,
        "chemical_potential",
    )
    assert holes["chemical_potential_k"][0] < -50.0
    assert electrons["chemical_potential_k"][0] > -50.0
    diagram = explicit_diagram(settings, p | {"band_offset_k": 100.0, "fermi_energy": 50.0}, 1, 1)
    assert "fermi_energy_lower_k" not in diagram.curves
    np.testing.assert_array_equal(diagram.curves["fermi_energy_k"], 50.0)


def test_explicit_valley_counts_are_integers():
    p = dict(m1=1.0, mass_ratio=1.0, band_offset_k=100.0)
    with pytest.raises(ValueError, match="integer"):
        explicit_curves(ExplicitBands("vb_cb", 0.0), "dpb_s", p, np.array([300.0]), "acPh", 1.5, 1)


def test_symmetric_intrinsic_transport_cancels_exactly_on_preview_grid():
    t = np.linspace(50, 800, 50)
    p = dict(m1=1.0, mass_ratio=1.0, band_offset_k=1000.0, fermi_energy=350.0, A=4e4, B=1.0)
    curves = explicit_curves(ExplicitBands("vb_cb"), "dpb_s_rho_rh", p, t, "acPh", 1, 1)

    np.testing.assert_array_equal(curves["seebeck_v_per_k"], 0.0)
    np.testing.assert_array_equal(curves["hall_m3_per_c"], 0.0)
    # Equal acoustic channels add, with F_0 evaluated at the exact midpoint.
    rho = 1 / (2 * p["A"] * np.logaddexp(0.0, -p["band_offset_k"] / (2 * t)))
    np.testing.assert_allclose(curves["resistivity_ohm_m"], rho, rtol=1e-12, atol=0)


@pytest.mark.parametrize("weight, sign", [(0.5, 1), (2.0, -1)])
def test_intrinsic_symmetric_bands_keep_asymmetric_transport_weight(weight, sign):
    t = np.array([800.0])
    p = dict(
        m1=1.0,
        mass_ratio=1.0,
        band_offset_k=3945.53616139,
        fermi_energy=1972.7680807,
        A=4e4,
        B=weight,
    )
    curves = explicit_curves(ExplicitBands("vb_cb"), "dpb_s_rho_rh", p, t, "acPh", 1, 1)

    # Independent SI quadrature gives |S_i|=388.39059 µV/K and |R_H,i|=8.117680e-7 m³/C.
    # Weighting the opposite contributions by (1/3, 2/3) gives one third of each magnitude.
    assert curves["seebeck_v_per_k"][0] == pytest.approx(sign * 129.463531e-6, rel=1e-6)
    assert curves["hall_m3_per_c"][0] == pytest.approx(sign * 2.70589333e-7, rel=1e-6)
