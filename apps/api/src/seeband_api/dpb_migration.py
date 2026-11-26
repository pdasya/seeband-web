"""Convert a historical DPB point with a researcher-supplied absolute DOS scale."""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from seeband_core.model_interface import BandConfiguration, ExplicitBands

from seeband_api.errors import ApiError
from seeband_api.request_checks import ParameterValues, PositiveFloat
from seeband_api.routing import api_router, too_many_requests

router = api_router("dpb")


class LegacyDpbPoint(BaseModel):
    parameters: ParameterValues
    m1: PositiveFloat
    band_1_degeneracy: PositiveFloat
    band_2_degeneracy: PositiveFloat


class ConvertedDpbPoint(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "parameterization": "explicit_density_v1",
                    "band_configuration": "vb_cb",
                    "net_electron_density_per_m3": 0.0,
                    "parameters": {"mass_ratio": 1.8, "band_offset_k": 600.0, "m1": 1.2},
                }
            ]
        }
    )

    parameterization: Literal["explicit_density_v1"] = "explicit_density_v1"
    band_configuration: BandConfiguration
    net_electron_density_per_m3: float
    parameters: dict[str, float]


@router.post("/dpb/migrate", responses={429: too_many_requests()})
def migrate_dpb(body: LegacyDpbPoint) -> ConvertedDpbPoint:
    from seeband_core.explicit_transport import zero_temperature_density

    p = body.parameters
    if not {"m_eff", "fermi_energy", "band_gap"} <= p.keys() or p.get("m_eff") == 0:
        raise ApiError(
            422, "invalid_legacy_bands", "Supply nonzero m_eff, band_gap and fermi_energy"
        )
    if p.keys() - {"m_eff", "fermi_energy", "band_gap", "m1", "A", "B", "F", "G", "C", "D"}:
        raise ApiError(422, "invalid_legacy_bands", "Unknown legacy parameter")
    config: BandConfiguration = "vb_cb" if p["m_eff"] > 0 else "vb_vb"
    transport_names = ("A", "B", "C", "D", "F", "G")
    values = {name: p[name] for name in transport_names if name in p}
    values.update(mass_ratio=abs(p["m_eff"]), band_offset_k=p["band_gap"], m1=body.m1)
    try:
        density = zero_temperature_density(
            config, values, p["fermi_energy"], body.band_1_degeneracy, body.band_2_degeneracy
        )
        ExplicitBands(config, density)
    except (ValueError, ArithmeticError) as exc:
        raise ApiError(422, "invalid_legacy_bands", str(exc)) from exc
    return ConvertedDpbPoint(
        band_configuration=config, net_electron_density_per_m3=density, parameters=values
    )
