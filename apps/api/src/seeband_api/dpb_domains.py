"""One manual control's transport domain with all other band parameters held fixed."""

from math import isfinite
from typing import Annotated, Literal

from fastapi import Query
from pydantic import BaseModel, ConfigDict, FiniteFloat
from seeband_core.model_interface import BandConfiguration, CarrierType, ExplicitBands

from seeband_api.errors import ApiError
from seeband_api.routing import api_router

router = api_router("dpb")
_Positive = Annotated[float, Query(gt=0, allow_inf_nan=False)]


class ParameterDomain(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"lower": None, "upper": 1000.0, "inclusive": False, "empty": False}]
        }
    )
    lower: float | None = None
    upper: float | None = None
    inclusive: bool = True
    empty: bool = False


@router.get("/dpb/parameter-domain")
def get_dpb_parameter_domain(
    name: Literal["fermi_energy", "band_offset_k", "mass_ratio"],
    band_configuration: BandConfiguration,
    fermi_energy: FiniteFloat,
    band_offset_k: FiniteFloat,
    mass_ratio: _Positive,
    band_1_degeneracy: _Positive,
    band_2_degeneracy: _Positive,
    carrier_type: CarrierType | None = None,
) -> ParameterDomain:
    from seeband_core.carrier_domain import carrier_domain

    try:
        if not float(band_1_degeneracy).is_integer() or not float(band_2_degeneracy).is_integer():
            raise ValueError("Valley counts must be positive integers")
        ExplicitBands(band_configuration, carrier_type=carrier_type)
        domain = carrier_domain(
            name,
            band_configuration,
            carrier_type,
            fermi_energy,
            band_offset_k,
            mass_ratio,
            band_1_degeneracy,
            band_2_degeneracy,
        )
    except (ValueError, ArithmeticError) as exc:
        raise ApiError(422, "invalid_band_parameters", str(exc)) from exc
    if domain is None:
        return ParameterDomain()
    lower, upper, inclusive = domain
    if lower == float("inf") or upper == -float("inf"):
        return ParameterDomain(empty=True)
    return ParameterDomain(
        lower=lower if lower is not None and isfinite(lower) else None,
        upper=upper if upper is not None and isfinite(upper) else None,
        inclusive=inclusive,
    )
