"""Recover independent forward values after a numerical exception, without changing formulas."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from seeband_core.fit_quality import CURVE_NAMES, Rmse, curve_rmse
from seeband_core.math_module import (
    NoFiniteChemicalPotentialError,
    reuse_chemical_potential,
)
from seeband_core.model_interface import CurveRequest, CurveResult, Measurement, Model, Quantity

# The curve kinds of dpb_s_rho_rh whose values depend on m1.
_KINDS_WITH_M1 = frozenset({"measured", "carrier_concentration_by_band"})


@dataclass(frozen=True)
class CalculationIssue:
    scope: Literal["curve", "rmse"]
    quantity: str
    temperature_k: tuple[float, ...]
    code: str


def _attempt(
    model: Model, request: CurveRequest
) -> tuple[CurveResult | None, ArithmeticError | ValueError | None]:
    """The curve, or the numerical error it raised."""
    try:
        result = model.calculate(request)
    except NoFiniteChemicalPotentialError:
        # Structurally invalid band parameters retain their request-level semantics.
        raise
    except (ArithmeticError, ValueError) as error:
        return None, error
    _refuse_complex(result.curves.values())
    return result, None


def _refuse_complex(arrays: Iterable[np.ndarray]) -> None:
    # A negative m1 gives complex values, whose real part would look like a plausible result.
    if any(np.iscomplexobj(values) for values in arrays):
        raise ValueError("The curve has complex values")


def partial_curve(
    model: Model, request: CurveRequest
) -> tuple[CurveResult, tuple[CalculationIssue, ...]]:
    """Use the original vector path when healthy; retry failed built-in curves at each T.

    No finite point is dropped from a successful vector result. Retries evaluate the same
    kernels on singleton grids; measured observables can additionally run independently.
    """
    from seeband_core.band_models import (
        _CURVE_NAMES,
        LORENZ_BAND_CURVES,
        LORENZ_CURVE,
        DpbModel,
        SpbModel,
    )
    from seeband_core.known_issues import active_issue_ids
    from seeband_core.verified_fit import evaluate

    explicit = request.explicit_bands
    if explicit is not None:
        if model.describe().id != "dpb":
            raise ValueError("Explicit band types require DPB")
        from seeband_core.model_descriptions import explicit_dpb_description

        mode = explicit_dpb_description(explicit.uses_fermi_energy).fit_mode(request.fit_mode)
    else:
        mode = model.describe().fit_mode(request.fit_mode)
    # Invalid controls, unavailable curves and missing parameters are never partial results.
    # Only the parameters of the chosen scattering are needed: C and D belong to acPhDis.
    active = mode.parameters_for(request.scattering)
    if request.kind not in mode.curve_kinds:
        raise ValueError("Unavailable curve")
    if any(spec.name not in request.parameters for spec in active):
        raise ValueError("Missing parameters")
    # A negative m1 is refused only where it enters: R_H in the measured vector and the band
    # densities. A partial result would otherwise keep S and rho and hide the invalid mass.
    if request.kind in _KINDS_WITH_M1 and request.parameters.get("m1", 0.0) < 0:
        raise ValueError("The Hall band mass must be nonnegative")
    with reuse_chemical_potential():
        curve, first_error = _attempt(model, request)
        failed: dict[str, list[float]] = {}
        if curve is None:
            if not isinstance(model, SpbModel | DpbModel):
                raise ValueError("The calculation failed")
            names = (
                tuple(CURVE_NAMES[q] for q in mode.quantities)
                if request.kind == "measured"
                else (LORENZ_CURVE, *LORENZ_BAND_CURVES)
                if request.kind == "lorenz_number" and isinstance(model, DpbModel)
                else (LORENZ_CURVE,)
                if request.kind == "lorenz_number"
                else _CURVE_NAMES[request.kind]
            )
            temperatures = np.linspace(
                request.min_temperature_k, request.max_temperature_k, request.points
            )
            values = {name: np.full(request.points, np.nan) for name in names}
            ratio = request.band_2_degeneracy / request.band_1_degeneracy
            for index, temperature in enumerate(temperatures):
                single = replace(
                    request,
                    min_temperature_k=float(temperature),
                    max_temperature_k=float(temperature),
                    points=1,
                )
                point, _ = _attempt(model, single)
                if point is None and request.kind == "measured":
                    # The Hall kernel runs last. Its absence must not erase the original S/rho.
                    if "hall" in mode.quantities:
                        lower = replace(single, fit_mode=f"{model.describe().id}_s_rho")
                        point, _ = _attempt(model, lower)
                    available = dict(point.curves) if point is not None else {}
                    for quantity in mode.quantities:
                        name = CURVE_NAMES[quantity]
                        if name in available:
                            continue
                        try:
                            if (
                                quantity != "seebeck"
                                and request.scattering != "ionized"
                                and explicit is None
                            ):
                                isolated = (
                                    replace(single, fit_mode=f"{model.describe().id}_s_rho")
                                    if quantity == "resistivity"
                                    else single
                                )
                                isolated_mode = model.describe().fit_mode(isolated.fit_mode)
                                function, arguments = model._curve_call(
                                    isolated, isolated_mode, request.scattering
                                )
                                result = function(
                                    float(temperature),
                                    float(temperature),
                                    1,
                                    *arguments,
                                    skip_seebeck=True,
                                )
                                available[name] = result[-1]
                            else:
                                available[name] = evaluate(
                                    model.describe().id,
                                    request.fit_mode,
                                    request.parameters,
                                    np.array([temperature]),
                                    request.scattering,
                                    ratio,
                                    quantities=(quantity,),
                                    check_finite=False,
                                    band_1_degeneracy=request.band_1_degeneracy,
                                    explicit_bands=explicit,
                                )[quantity]
                            _refuse_complex([available[name]])
                        except NoFiniteChemicalPotentialError:
                            raise
                        except (ArithmeticError, ValueError):
                            pass
                    point = CurveResult(np.array([temperature]), available)
                for name in names:
                    if point is not None and name in point.curves:
                        values[name][index] = point.curves[name][0]
                    else:
                        failed.setdefault(name, []).append(float(temperature))
            if not any(np.any(np.isfinite(array)) for array in values.values()):
                # Keep the request-level failure of the whole curve if nothing was recovered.
                assert first_error is not None
                raise first_error
            curve = CurveResult(
                temperatures,
                values,
                active_issue_ids(
                    mode,
                    request.scattering,
                    request.parameters,
                    ratio,
                    request.kind,
                    request.extrapolated,
                ),
            )
    issues = []
    for name, array in curve.curves.items():
        thrown = failed.get(name, [])
        if thrown:
            issues.append(CalculationIssue("curve", name, tuple(thrown), "calculation_failed"))
        thrown_set = set(thrown)
        nonfinite = [
            float(t)
            for t, value in zip(curve.temperature_k, array, strict=True)
            if not np.isfinite(value) and float(t) not in thrown_set
        ]
        if nonfinite:
            issues.append(CalculationIssue("curve", name, tuple(nonfinite), "non_finite_result"))
    return curve, tuple(issues)


def partial_rmse(
    model: Model,
    request: CurveRequest,
    measurements: Mapping[Quantity, Measurement],
    points: int,
) -> tuple[dict[Quantity, Rmse], tuple[CalculationIssue, ...]]:
    """Retain the shared-grid healthy path and isolate failed comparisons by observable."""
    if not measurements:
        return {}, ()

    def compare(data: Mapping[Quantity, Measurement]) -> dict[Quantity, Rmse]:
        return curve_rmse(
            model,
            request.fit_mode,
            request.parameters,
            data,
            request.scattering,
            request.band_1_degeneracy,
            request.band_2_degeneracy,
            points,
            explicit_bands=request.explicit_bands,
        )

    try:
        results = compare(measurements)
    except (ArithmeticError, ValueError):
        results = {}
    issues = []
    for quantity, measurement in measurements.items():
        unit = "uV/K" if quantity == "seebeck" else "%"
        zeros = measurement.values == 0
        if quantity != "seebeck" and np.any(zeros):
            results[quantity] = Rmse(None, unit)
            issues.append(
                CalculationIssue(
                    "rmse",
                    quantity,
                    tuple(map(float, measurement.temperature_k[zeros])),
                    "zero_measured_value",
                )
            )
            continue
        code = "non_finite_result"
        if quantity not in results:
            try:
                results[quantity] = compare({quantity: measurement})[quantity]
            except (ArithmeticError, ValueError) as error:
                results[quantity] = Rmse(None, unit)
                code = getattr(error, "code", None) or "calculation_failed"
        result = results[quantity]
        if result.value is not None and np.isfinite(result.value):
            continue
        results[quantity] = Rmse(None, unit)
        # A scalar RMSE has no value if any comparison is missing. Probe only its diagnostic
        # locations; never compute an RMSE from a reduced subset of observations.
        failed: dict[str, list[float]] = {}
        for temperature, value in zip(measurement.temperature_k, measurement.values, strict=True):
            point = Measurement(np.array([temperature]), np.array([value]))
            try:
                check = compare({quantity: point})[quantity]
                point_code = "non_finite_result"
                bad = check.value is None or not np.isfinite(check.value)
            except (ArithmeticError, ValueError) as error:
                bad = True
                point_code = getattr(error, "code", None) or "calculation_failed"
            if bad:
                failed.setdefault(point_code, []).append(float(temperature))
        if not failed:
            failed[code] = list(map(float, measurement.temperature_k))
        issues.extend(
            CalculationIssue("rmse", quantity, tuple(temperatures), issue_code)
            for issue_code, temperatures in failed.items()
        )
    return results, tuple(issues)
