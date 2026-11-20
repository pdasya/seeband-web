"""Convert a historical DPB point with a researcher-supplied absolute DOS scale."""

from typing import Literal

from pydantic import BaseModel
from seeband_core.model_interface import BandConfiguration, ExplicitBands

from seeband_api.errors import ApiError
from seeband_api.request_checks import ParameterValues, PositiveFloat
from seeband_api.routing import api_router

router = api_router("dpb")


class LegacyDpbPoint(BaseModel):
    parameters: ParameterValues
    m1: PositiveFloat
    band_1_degeneracy: PositiveFloat
    band_2_degeneracy: PositiveFloat


class ConvertedDpbPoint(BaseModel):
    parameterization: Literal["explicit_density_v1"] = "explicit_density_v1"
    band_configuration: BandConfiguration
    net_electron_density_per_m3: float
    parameters: dict[str, float]


@router.post("/dpb/migrate")
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
    values: dict[str, float] = {name: p[name] for name in ("A", "B", "F", "G") if name in p}
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
