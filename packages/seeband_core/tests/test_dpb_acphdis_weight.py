"""P11: combined scattering weights belong to each temperature, independently of the grid."""

import numpy as np
import pytest
from seeband_core import fit_module, math_module
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest
from seeband_core.model_scales import default_start

# These identities reuse the same transport integrals and charge solver, so only
# floating-point arithmetic roundoff is allowed; no fit or table tolerance is needed.
ROUND_OFF_RTOL = 1e-12


def test_300_k_seebeck_is_unchanged_when_800_k_is_added():
    parameters = (1.0, 300.0, -100.0, 1.0, 1.0, 150.0, 600.0)
    singleton = math_module.dpb_see_vs_temp_double_scatter(np.array([300.0]), *parameters)
    batch = math_module.dpb_see_vs_temp_double_scatter(np.array([300.0, 800.0]), *parameters)
    np.testing.assert_allclose(batch[:1], singleton, rtol=ROUND_OFF_RTOL, atol=0)


@pytest.mark.parametrize(
    "temperature_k",
    [
        [100.0, 300.0, 500.0, 800.0],
        [800.0, 500.0, 300.0, 100.0],
        [500.0, 100.0, 800.0, 300.0],
        [300.0, 800.0],
        [300.0, 100.0, 300.0, 800.0, 100.0],
    ],
    ids=["ascending", "descending", "shuffled", "subset", "duplicates"],
)
@pytest.mark.parametrize("meff", [1.0, -2.0])
@pytest.mark.parametrize("degen", [1.0, 3.0])
def test_every_batch_point_matches_its_singleton(temperature_k, meff, degen):
    temperature_k = np.array(temperature_k)
    parameters = (meff, 300.0, -100.0, degen, 0.4, 150.0, 600.0)
    expected = np.array(
        [
            math_module.dpb_see_vs_temp_double_scatter(np.array([temp]), *parameters)[0]
            for temp in temperature_k
        ]
    )
    actual = math_module.dpb_see_vs_temp_double_scatter(temperature_k, *parameters)
    np.testing.assert_allclose(actual, expected, rtol=ROUND_OFF_RTOL, atol=0)


@pytest.mark.parametrize("meff", [1.0, -2.0])
@pytest.mark.parametrize("degen", [1.0, 3.0])
@pytest.mark.parametrize("scale", [1.0, -7.25, 1e6])
def test_total_uses_explicit_pointwise_transport_weight_and_equals_band_sum(meff, degen, scale):
    temperature_k = np.array([100.0, 300.0, 500.0, 800.0])
    gap, fermi_energy, b, c_k, d_k = 300.0, -100.0, 0.4, 150.0, 600.0
    potentials = math_module.dpb_chemPot_vs_temp(temperature_k, gap, meff, fermi_energy, degen)
    expected = []
    for temp, mu in zip(temperature_k, potentials, strict=True):
        sigma1 = math_module.sigma_general(mu, -1, 1, -1, temp)
        sigma2 = math_module.sigma_general(mu - gap, np.sign(meff), 1, -1, temp)
        onsager1 = math_module.onsi_general(mu, -1, 1, -1, temp)
        onsager2 = math_module.onsi_general(mu - gap, np.sign(meff), 1, -1, temp)
        weight = b * (c_k + temp) / (d_k + temp) / meff
        conductivity = sigma1 + weight * sigma2
        # Keep the signed-mass cases well away from a zero-conductivity pole.
        assert abs(conductivity) > 0.1 * (abs(sigma1) + abs(weight * sigma2))
        expected.append(scale * (onsager1 + weight * onsager2) / conductivity)

    parameters = (meff, gap, fermi_energy, degen, b, c_k, d_k)
    actual = math_module.dpb_see_vs_temp_double_scatter(temperature_k, *parameters, scal_fac=scale)
    band1, band2 = math_module.dpb_indCont_see_vs_temp_double_scatter(
        temperature_k, *parameters, scal_fac=scale
    )
    np.testing.assert_allclose(actual, expected, rtol=ROUND_OFF_RTOL, atol=0)
    np.testing.assert_allclose(actual, band1 + band2, rtol=ROUND_OFF_RTOL, atol=0)


@pytest.mark.parametrize("meff", [1.0, -2.0])
@pytest.mark.parametrize("degen", [1.0, 3.0])
def test_equal_c_and_d_reduce_to_constant_single_scattering_weight(meff, degen):
    temperature_k = np.array([100.0, 300.0, 800.0])
    parameters = (meff, 300.0, -100.0, degen, 0.4)
    actual = math_module.dpb_see_vs_temp_double_scatter(
        temperature_k, *parameters, 450.0, 450.0, scal_fac=7.25
    )
    expected = math_module.dpb_see_vs_temp_single_scatter(temperature_k, *parameters, scal_fac=7.25)
    np.testing.assert_allclose(actual, expected, rtol=ROUND_OFF_RTOL, atol=0)


def test_fit_objective_uses_the_same_pointwise_kernel():
    temperature_k = np.array([100.0, 300.0, 800.0])
    parameters = (1.0, 300.0, -100.0)
    objective = fit_module._dpb_see_model_double_scatter(temperature_k, 1.0, 1.0, 150.0, 600.0)
    expected = np.array(
        [
            math_module.dpb_see_vs_temp_double_scatter(
                np.array([temp]), *parameters, 1.0, 1.0, 150.0, 600.0, scal_fac=1e6
            )[0]
            for temp in temperature_k
        ]
    )
    np.testing.assert_allclose(
        objective(temperature_k, *parameters), expected, rtol=ROUND_OFF_RTOL, atol=0
    )


@pytest.mark.parametrize("mode_id", ["dpb_s_rho", "dpb_s_rho_rh"])
@pytest.mark.parametrize("degen", [1.0, 3.0])
def test_registry_measured_seebeck_equals_derived_band_sum(mode_id, degen):
    model = registry.get("dpb")
    parameters = default_start(model.describe().fit_mode(mode_id)) | {
        "m_eff": 1.0,
        "band_gap": 300.0,
        "fermi_energy": -100.0,
        "B": 1.0,
        "C": 0.5,
        "D": 2.0,
    }

    def curve(kind):
        return model.calculate(
            CurveRequest(mode_id, parameters, 100, 800, 4, "acPhDis", kind, band_2_degeneracy=degen)
        )

    measured = curve("measured")
    bands = curve("seebeck_by_band")
    expected = math_module.dpb_see_vs_temp_double_scatter(
        measured.temperature_k, 1.0 / degen, 300.0, -100.0, degen, 1.0, 150.0, 600.0
    )
    np.testing.assert_allclose(
        measured.curves["seebeck_v_per_k"], expected, rtol=ROUND_OFF_RTOL, atol=0
    )
    np.testing.assert_allclose(
        measured.curves["seebeck_v_per_k"],
        sum(bands.curves.values()),
        rtol=ROUND_OFF_RTOL,
        atol=0,
    )


def test_zero_second_band_transport_weight_recovers_band_one_seebeck():
    t = np.array([300.0, 800.0])
    mu = math_module.dpb_chemPot_vs_temp(t, 300.0, 1.0, -100.0, 1.0)
    expected = [
        math_module.onsi_general(value, -1.0, 1.0, -1.0, temperature)
        / math_module.sigma_general(value, -1.0, 1.0, -1.0, temperature)
        for temperature, value in zip(t, mu, strict=True)
    ]
    actual = math_module.dpb_see_vs_temp_double_scatter(
        t, 1.0, 300.0, -100.0, 1.0, 0.0, 150.0, 600.0
    )
    np.testing.assert_allclose(actual, expected, rtol=ROUND_OFF_RTOL, atol=0)


def test_other_quantity_temperature_extent_cannot_change_seebeck_rmse():
    from seeband_core.fit_quality import curve_rmse
    from seeband_core.model_interface import Measurement

    model = registry.get("dpb")
    parameters = default_start(model.describe().fit_mode("dpb_s_rho")) | {
        "m_eff": 1.0,
        "band_gap": 300.0,
        "fermi_energy": -100.0,
        "B": 1.0,
        "C": 0.5,
        "D": 2.0,
    }
    point = model.calculate(CurveRequest("dpb_s_rho", parameters, 300, 300, 1, "acPhDis"))
    for rho_temperature in [800.0, 1000.0]:
        measurements = {
            "seebeck": Measurement(np.array([300.0]), point.curves["seebeck_v_per_k"]),
            "resistivity": Measurement(np.array([rho_temperature]), np.array([1.0])),
        }
        result = curve_rmse(model, "dpb_s_rho", parameters, measurements, "acPhDis")
        # 300 K is an exact endpoint of both RMSE grids: no interpolation approximation is involved.
        assert result["seebeck"].value == 0.0
