"""Physical identities for P3: core C and D are dimensionless ratios at 300 K."""

import numpy as np
import pytest
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest
from seeband_core.model_scales import default_start


@pytest.mark.parametrize("mode_id", ["spb_s_rho", "dpb_s_rho", "dpb_s_rho_rh"])
@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis"])
def test_conductivity_is_inverse_resistivity(mode_id: str, scattering: str) -> None:
    model = registry.get(mode_id.partition("_")[0])
    mode = model.describe().fit_mode(mode_id)
    parameters = default_start(mode) | {"C": 0.5}
    if mode_id.startswith("dpb"):
        parameters |= {"D": 2.0, "m_eff": 1.2, "band_gap": 800.0, "fermi_energy": -150.0}

    def calculate(kind: str) -> dict[str, np.ndarray]:
        return model.calculate(
            CurveRequest(mode_id, parameters, 50, 800, 16, scattering, kind)
        ).curves

    rho = calculate("measured")["resistivity_ohm_m"]
    sigma = calculate("electrical_conductivity")["electrical_conductivity_s_per_m"]
    np.testing.assert_allclose(sigma * rho, 1.0, rtol=1e-10, atol=0)


@pytest.mark.parametrize("model_id", ["spb", "dpb"])
def test_thermal_conductivity_uses_the_same_scattering_scale(model_id: str) -> None:
    from seeband_core import math_module as math

    mode_id = model_id + "_s_rho"
    model = registry.get(model_id)
    parameters = default_start(model.describe().fit_mode(mode_id)) | {"C": 0.5}
    if model_id == "dpb":
        parameters |= {"D": 2.0, "m_eff": 1.2, "band_gap": 800.0, "fermi_energy": -150.0}

    def curve(kind: str):
        return model.calculate(CurveRequest(mode_id, parameters, 100, 800, 8, "acPhDis", kind))

    thermal = curve("thermal_conductivity")
    t = thermal.temperature_k
    if model_id == "spb":
        sigma = curve("electrical_conductivity").curves["electrical_conductivity_s_per_m"]
        lorenz = math.spb_lorNum_vs_temp(t, parameters["fermi_energy"], parameters["band_mass"])
        expected = lorenz * sigma * t
    else:
        sigma = list(curve("electrical_conductivity_by_band").curves.values())
        total_sigma = sigma[0] + sigma[1]
        np.testing.assert_allclose(
            total_sigma,
            curve("electrical_conductivity").curves["electrical_conductivity_s_per_m"],
            rtol=1e-10,
        )
        seebeck = list(curve("seebeck_by_band").curves.values())
        own_s = [
            s * total_sigma / conductivity for s, conductivity in zip(seebeck, sigma, strict=True)
        ]
        lorenz = math.dpb_lorNum_vs_temp(
            t, parameters["m_eff"], parameters["band_gap"], parameters["fermi_energy"], 1.0
        )
        expected = t * (lorenz[0] * sigma[0] + lorenz[1] * sigma[1])
        expected += t * sigma[0] * sigma[1] / total_sigma * (own_s[0] - own_s[1]) ** 2
        # Also cross-check individual points; P11 tests the complete-grid sum separately.
        for temperature in t:
            point = model.calculate(
                CurveRequest(mode_id, parameters, temperature, temperature, 1, "acPhDis")
            )
            bands = model.calculate(
                CurveRequest(
                    mode_id, parameters, temperature, temperature, 1, "acPhDis", "seebeck_by_band"
                )
            )
            np.testing.assert_allclose(
                sum(bands.curves.values()), point.curves["seebeck_v_per_k"], rtol=1e-10, atol=1e-18
            )
    np.testing.assert_allclose(
        thermal.curves["thermal_conductivity_w_per_m_k"], expected, rtol=1e-10, atol=1e-18
    )
