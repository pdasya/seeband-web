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
