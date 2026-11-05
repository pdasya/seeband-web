"""Replay every call recorded from the desktop window through the ported modules.

Golden results were captured on one Mac with Python 3.11, numpy 1.26 and scipy 1.17. The project
uses newer versions, and CI runs on Linux, so this is the check across versions and machines.
docs/golden-results.md gives the measured differences.

CURVE_TOLERANCE is tight, because curves are direct calculations. FIT_TOLERANCE is looser, because
fits depend on the solver. A small change can stay within FIT_TOLERANCE, but the curves catch it.

Some fits are not reproducible across versions: see UNSTABLE_02 and deviation D19.

The replay goes through the model interface, so it also checks SPB and DPB in band_models. Recorded
calls name their arguments through the core's signatures, in recorded_arguments. When a refactor
renames a function or drops an argument, update these and leave the pinned fixtures unchanged. The
input tests call the core directly, through core_arguments and invoke_core. The test of
spb_see_res_hall_fit has no recorded call, so it names the function and its argument order itself.
"""

import contextlib
import copy
import inspect
import json
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core import fit_module
from seeband_core.band_models import parabolic_band
from seeband_core.model_catalog import registry as default_registry
from seeband_core.model_interface import (
    Bounds,
    CurveKind,
    CurveRequest,
    FitRequest,
    Measurement,
    Quantity,
)

GOLDEN = Path(__file__).parent / "fixtures" / "golden"
EXAMPLES = ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]
CURVE_TOLERANCE = 1e-9
FIT_TOLERANCE = 1e-5
# Number of leading arguments that are measurement arrays in each fit function.
ARRAY_ARGUMENTS = {
    "spb_see_fit": 2,
    "spb_see_res_fit": 4,
    "spb_see_res_hall_fit": 6,
    "dpb_see_fit": 2,
    "dpb_see_res_fit": 4,
    "dpb_see_res_hall_fit": 6,
}
# Fits that the desktop called with print_info as a further positional argument.
POSITIONAL_ARGUMENTS = {"dpb_see_res_fit": 12, "dpb_see_res_hall_fit": 16}
# Error text can change with a scipy update, so only a stable part of it is compared.
ERROR_FRAGMENTS = {"ValueError": "bounds"}
# These fits are not stable across versions or machines (D19).
UNSTABLE_02 = {
    ("dpb_s", None),
    ("dpb_s_rho", "acPh"),
    ("dpb_s_rho", "dis"),
    ("dpb_s_rho", "acPhDis"),
    ("dpb_s_rho_rh", "acPh"),
    ("dpb_s_rho_rh", "acPhDis"),
    ("d1", "dis"),
}
COLLAPSED_M_EFF = 1e-5
# The G minimum case on 01 is not credible either, and differs by about 1e-4.
D1_01_TOLERANCE = 1e-3
# E_F on 02_SiP with SPB S falls from 100 to 3.76 with solver warnings. It differed by 3.4e-6 on a
# Mac, and by 1.8e-5 and 2.8e-5 in two Linux CI runs, so it varies between runs of the same code.
SPB_S_02_TOLERANCE = 1e-4
# Public methods with no recorded call. The fit is unreachable on the desktop because of D2, and
# is_accuracy_reached is covered through the fits that call it.
NOT_COVERED = {"spb_see_res_hall_fit", "is_accuracy_reached"}


def recorded_calls() -> Iterator[tuple[str, str, str | None, str, dict[str, Any]]]:
    for example in EXAMPLES:
        document = json.loads((GOLDEN / f"{example}.json").read_text(encoding="utf-8"))
        for run in document["runs"]:
            for call in run["calls"]:
                yield example, run["mode"], run["scattering"], "thread", call
            for call in run["manual_curve_calls"]:
                yield example, run["mode"], run["scattering"], "slider", call
            for graph in run["graph_buttons"]:
                for call in graph["calls"]:
                    yield example, run["mode"], run["scattering"], graph["button"], call
        for call in document["d1_with_g_minimum_1"]["calls"]:
            yield example, "d1", "dis", "thread", call


CALLS = list(recorded_calls())
CALL_IDS = [
    f"{example}-{mode}-{scattering}-{source}-{call['function']}"
    for example, mode, scattering, source, call in CALLS
]


def core_arguments(
    function: str, args: list[Any], kwargs: dict[str, Any]
) -> tuple[list[Any], dict[str, Any]]:
    """Turn recorded arguments into what the core takes today."""
    arrays = ARRAY_ARGUMENTS.get(function, 0)
    converted = [np.array(value) if index < arrays else value for index, value in enumerate(args)]
    # The desktop also passed print_info, which the core no longer has.
    converted = converted[: POSITIONAL_ARGUMENTS.get(function)]
    return converted, {name: value for name, value in kwargs.items() if name != "print_info"}


def invoke_core(function: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
    return getattr(fit_module.PB_fit(), function)(*args, **kwargs)


CURVE_KINDS: dict[str, CurveKind] = {
    "spb_see_calc": "measured",
    "spb_see_res_calc": "measured",
    "spb_see_res_hall_calc": "measured",
    "dpb_see_calc": "measured",
    "dpb_see_res_calc": "measured",
    "dpb_see_res_hall_calc": "measured",
    "dpb_see_with_scatter_calc": "seebeck",
    "spb_chemPot_calc": "chemical_potential",
    "dpb_chemPot_calc": "chemical_potential",
    "spb_elecCond_calc": "electrical_conductivity",
    "dpb_elecCond_calc": "electrical_conductivity",
    "spb_thermCond_calc": "thermal_conductivity",
    "dpb_thermCond_calc": "thermal_conductivity",
    "dpb_ind_see_seeOnly_calc": "seebeck_by_band",
    "dpb_ind_see_calc": "seebeck_by_band",
    "dpb_ind_elecCond_calc": "electrical_conductivity_by_band",
    "dpb_ind_carCon_calc": "carrier_concentration_by_band",
    "dpb_ind_carCon_calc_m1": "carrier_concentration_by_band",
}
SPB_SCATTERING = ("A", "C", "F")
DPB_BANDS = ("m_eff", "band_gap", "fermi_energy")
DPB_SCATTERING = ("A", "B", "C", "D", "F", "G")
# The order of each fit's recorded result.
FIT_RESULT_NAMES = {
    "spb_see_fit": ("fermi_energy",),
    "spb_see_res_fit": ("fermi_energy", *SPB_SCATTERING),
    "dpb_see_fit": DPB_BANDS,
    "dpb_see_res_fit": (*DPB_BANDS, *DPB_SCATTERING),
    "dpb_see_res_hall_fit": (*DPB_BANDS, *DPB_SCATTERING, "m1"),
}


def recorded_arguments(call: dict[str, Any]) -> dict[str, Any]:
    """Name a recorded call's arguments from the core's signature, without print_info."""
    function = getattr(fit_module.PB_fit, call["function"])
    args, kwargs = core_arguments(
        call["function"],
        json.loads(json.dumps(call["args"])),
        json.loads(json.dumps(call["kwargs"])),
    )
    return dict(inspect.signature(function).bind(None, *args, **kwargs).arguments)


def named(names: tuple[str, ...], values: list[Any]) -> dict[str, Any]:
    return dict(zip(names, values, strict=True))


def named_bounds(names: tuple[str, ...], limits: list[list[float]]) -> dict[str, Bounds]:
    return {
        name: Bounds(lower, upper)
        for name, lower, upper in zip(names, limits[0], limits[1], strict=True)
    }


def fit_request(fit_mode: str, call: dict[str, Any]) -> FitRequest:
    a = recorded_arguments(call)
    temperature_see = a.get("temp_see_list", a.get("temp_list"))
    measurements: dict[Quantity, Measurement] = {
        "seebeck": Measurement(temperature_see, a.get("see_list"))
    }
    if "res_list" in a:
        measurements["resistivity"] = Measurement(a["temp_res_list"], a["res_list"])
    if "hall_list" in a:
        measurements["hall"] = Measurement(a["temp_hall_list"], a["hall_list"])
    start: dict[str, Any] = {}
    bounds: dict[str, Bounds] = {}
    if "band_mass" in a:
        start["band_mass"] = a["band_mass"]
        start["fermi_energy"] = a["initial_fermi_energy"][0]
        bounds |= named_bounds(("fermi_energy",), a["limits_fermi_energy"])
        if "initial_parameter_res" in a:
            start |= named(SPB_SCATTERING, a["initial_parameter_res"])
            bounds |= named_bounds(SPB_SCATTERING, a["limits_res"])
    else:
        start |= named(DPB_BANDS, a.get("initial_parameter_see", a.get("initial_parameter")))
        bounds |= named_bounds(DPB_BANDS, a.get("limits_see", a.get("limits")))
        if "initial_parameter_res" in a:
            start |= named(DPB_SCATTERING, a["initial_parameter_res"])
            bounds |= named_bounds(DPB_SCATTERING, a["limits_res"])
    if "initial_mass1" in a:
        start["m1"] = a["initial_mass1"]
        bounds |= named_bounds(("m1",), a["limits_mass1"])
    if "threshold" in a:
        described = default_registry.get("dpb").describe().fit_mode(fit_mode)
        assert (a["threshold"], a["max_num_iterations"]) == (
            described.threshold,
            described.max_iterations,
        )
    return FitRequest(
        fit_mode,
        measurements,
        start,
        bounds,
        a.get("scatter_type"),
        band_2_degeneracy=a.get("degen", 1.0),
    )


def curve_request(fit_mode: str, scattering: str | None, call: dict[str, Any]) -> CurveRequest:
    a = recorded_arguments(call)
    parameters: dict[str, Any] = {}
    if "band_mass" in a:
        parameters["band_mass"] = a["band_mass"]
        parameters["fermi_energy"] = a["fermi_energy"]
    if "parameter_see" in a:
        parameters |= named(DPB_BANDS, a["parameter_see"])
    if "parameter_res" in a:
        names = SPB_SCATTERING if fit_mode.startswith("spb") else DPB_SCATTERING
        parameters |= named(names, a["parameter_res"])
    if "band_mass1" in a or "m1" in a:
        parameters["m1"] = a.get("band_mass1", a.get("m1"))
    return CurveRequest(
        fit_mode,
        parameters,
        a["Tmin"],
        a["Tmax"],
        a["Tnumb"],
        a.get("scatter_type", scattering),
        CURVE_KINDS[call["function"]],
        band_2_degeneracy=a.get("degen", 1.0),
    )


def replay(mode: str, scattering: str | None, call: dict[str, Any]) -> Any:
    """Run a recorded desktop call through the model interface, and return it in recorded order."""
    function = call["function"]
    if function == "get_parabolic_band":
        return list(parabolic_band(*call["args"]))
    fit_mode = "dpb_s_rho_rh" if mode == "d1" else mode
    model = default_registry.get(fit_mode.partition("_")[0])
    if function.endswith("_fit"):
        result = model.fit(fit_request(fit_mode, call))
        return [result.parameters[name] for name in FIT_RESULT_NAMES[function]]
    curve = model.calculate(curve_request(fit_mode, scattering, call))
    return [curve.temperature_k, *curve.curves.values()]


def flat(value: Any) -> Iterator[float]:
    if isinstance(value, list | tuple):
        for item in value:
            yield from flat(item)
    elif hasattr(value, "tolist"):
        yield from flat(value.tolist())
    else:
        yield float(value)


def assert_close(actual: Any, expected: Any, tolerance: float) -> None:
    got, recorded = list(flat(actual)), list(flat(expected))
    assert len(got) == len(recorded)
    for index, (x, y) in enumerate(zip(got, recorded, strict=True)):
        if math.isfinite(y):
            assert abs(x - y) <= tolerance * abs(y), f"value {index}: {x} vs {y}"
        else:
            assert x == y or (math.isnan(x) and math.isnan(y)), f"value {index}: {x} vs {y}"


def bounds_received(function: str, args: list[Any]) -> list[tuple[float, float]]:
    """Return the bounds of each parameter in result order, from a recorded DPB fit call."""
    arrays = ARRAY_ARGUMENTS[function]
    see = args[arrays + 1]
    pairs = list(zip(see[0], see[1], strict=True))
    if function != "dpb_see_fit":
        res = args[arrays + 3]
        pairs += list(zip(res[0], res[1], strict=True))
    if function == "dpb_see_res_hall_fit":
        pairs.append((args[arrays + 5][0][0], args[arrays + 5][1][0]))
    return pairs


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("example", "mode", "scattering", "source", "call"), CALLS, ids=CALL_IDS)
def test_replay_matches_the_desktop(
    example: str, mode: str, scattering: str | None, source: str, call: dict[str, Any]
) -> None:
    if "error" in call:
        kind, _, message = call["error"].partition(": ")
        with pytest.raises(Exception) as caught:
            replay(mode, scattering, call)
        assert type(caught.value).__name__ == kind
        assert ERROR_FRAGMENTS.get(kind, message) in str(caught.value)
        return

    result = replay(mode, scattering, call)
    if not call["function"].endswith("_fit"):
        assert_close(result, call["result"], CURVE_TOLERANCE)
    elif example == "02_SiP" and (mode, scattering) in UNSTABLE_02:
        values, recorded = list(flat(result)), list(flat(call["result"]))
        assert len(values) == len(recorded)
        assert abs(values[0]) < COLLAPSED_M_EFF
        assert_close(values[1:3], recorded[1:3], FIT_TOLERANCE)
        bounds = bounds_received(call["function"], call["args"])
        fitted = [(v, b) for v, b in zip(values, bounds, strict=False)]
        for value, (lower, upper) in fitted[:3]:
            assert lower <= value <= upper
    elif example == "01_Fe2VAl09Si01" and mode == "d1":
        assert_close(result, call["result"], D1_01_TOLERANCE)
    elif example == "02_SiP" and mode == "spb_s":
        assert_close(result, call["result"], SPB_S_02_TOLERANCE)
    else:
        assert_close(result, call["result"], FIT_TOLERANCE)


def same_value(first: Any, second: Any) -> bool:
    if isinstance(first, np.ndarray):
        return isinstance(second, np.ndarray) and np.array_equal(first, second)
    if isinstance(first, list | tuple):
        return (
            type(first) is type(second)
            and len(first) == len(second)
            and all(same_value(x, y) for x, y in zip(first, second, strict=True))
        )
    return bool(first == second)


def calls_with_distinct_inputs() -> list[dict[str, Any]]:
    distinct = {
        json.dumps([call["function"], call["args"], call["kwargs"]]): call for *_, call in CALLS
    }
    return list(distinct.values())


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("call", calls_with_distinct_inputs(), ids=lambda call: call["function"])
def test_recorded_calls_leave_their_inputs_unchanged(call: dict[str, Any]) -> None:
    recorded_args, recorded_kwargs = copy.deepcopy(call["args"]), copy.deepcopy(call["kwargs"])
    args, kwargs = core_arguments(call["function"], recorded_args, recorded_kwargs)
    args_before, kwargs_before = copy.deepcopy(args), copy.deepcopy(kwargs)
    with contextlib.suppress(ValueError):
        invoke_core(call["function"], args, kwargs)
    assert same_value(args, args_before)
    assert same_value(kwargs, kwargs_before)


def first_call(document: dict[str, Any], function: str) -> dict[str, Any]:
    calls = (call for run in document["runs"] for call in run["calls"])
    return next(call for call in calls if call["function"] == function and "error" not in call)


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("scatter_type", ["acPh", "dis", "acPhDis"])
def test_spb_hall_fit_leaves_its_inputs_unchanged(scatter_type: str) -> None:
    # This fit has no recorded call (D2), so its arguments are built from other recorded fits. A
    # whole-number mass gets past the type error that a float mass causes at its start.
    document = json.loads((GOLDEN / "03_AWI32_SI.json").read_text(encoding="utf-8"))
    data = first_call(document, "dpb_see_res_hall_fit")["args"][:6]
    start = first_call(document, "spb_see_res_fit")["args"][5:9]
    args, kwargs = core_arguments(
        "spb_see_res_hall_fit", [*data, *start, [-1], ([0], [10]), scatter_type], {}
    )
    args_before = copy.deepcopy(args)
    result = invoke_core("spb_see_res_hall_fit", args, kwargs)
    assert len(result) == 5
    assert same_value(args, args_before)


def count_function_entries(node: Any) -> int:
    """Count recorded calls by another route, so a new fixture section cannot be missed."""
    if isinstance(node, dict):
        return int("function" in node) + sum(count_function_entries(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_function_entries(item) for item in node)
    return 0


def test_every_recorded_call_is_replayed() -> None:
    documents = [json.loads((GOLDEN / f"{name}.json").read_text("utf-8")) for name in EXAMPLES]
    assert len(CALLS) == sum(count_function_entries(document) for document in documents)


def test_coverage_of_public_methods_is_as_documented() -> None:
    public = {
        name
        for name in dir(fit_module.PB_fit)
        if not name.startswith("_") and callable(getattr(fit_module.PB_fit, name))
    }
    called = {call["function"] for *_, call in CALLS}
    assert public - called == NOT_COVERED


def test_unstable_list_only_holds_cases_that_exist() -> None:
    found = {(mode, scattering) for example, mode, scattering, *_ in CALLS if example == "02_SiP"}
    assert UNSTABLE_02 <= found
