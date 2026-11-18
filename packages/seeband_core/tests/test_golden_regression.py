"""Replay historical desktop inputs against desktop and generated regression expectations.

Golden results were captured on one Mac with Python 3.11, numpy 1.26 and scipy 1.17. The project
uses newer versions, and CI runs on Linux, so this is the check across versions and machines.
P8, P11, P13 and P14 expectations are recorded separately. The desktop recordings are preserved.
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
import hashlib
import inspect
import json
import math
from collections.abc import Iterator
from functools import cache
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
    FitResult,
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


@cache
def p8_results() -> dict[str, Any]:
    return json.loads((GOLDEN.parent / "physics" / "p8.json").read_text())["results"]


# Only these acPhDis entry points call the repaired total-Seebeck kernel.
P11_FUNCTIONS = {
    "dpb_see_res_fit",
    "dpb_see_res_hall_fit",
    "dpb_see_res_calc",
    "dpb_see_res_hall_calc",
    "dpb_see_with_scatter_calc",
}

P11_REFITTED_PARAMETERS = {"m_eff", "band_gap", "fermi_energy", "A", "B", "C", "D", "m1"}


@cache
def p11_results() -> dict[str, Any]:
    """Implementation-generated regressions; independent desktop evidence is kept below."""
    return json.loads((GOLDEN.parent / "physics" / "p11.json").read_text())["results"]


def affected_by_p11(scattering: str | None, call: dict[str, Any]) -> bool:
    return scattering == "acPhDis" and call["function"] in P11_FUNCTIONS


P13_FUNCTIONS = {"dpb_see_fit", "dpb_see_res_fit", "dpb_see_res_hall_fit"}


@cache
def p13_results() -> dict[str, Any]:
    """Branch-constrained fit regressions, separate from desktop/P8/P11 evidence."""
    return json.loads((GOLDEN.parent / "physics" / "p13.json").read_text())["results"]


def regression_expected(identifier: str, scattering: str | None, call: dict[str, Any]) -> Any:
    if call["function"] in P13_FUNCTIONS:
        return p13_results()[p8_key(identifier, call)]
    expected = p8_results()[p8_key(identifier, call)]
    if not affected_by_p11(scattering, call):
        return expected
    corrected = p11_results()[p8_key(identifier, call)]
    if call["function"].endswith("_fit"):
        # Unused scattering fields and the status/message contract remain pinned
        # to P8; only refitted parameters and the iteration count can change.
        return expected | {
            "parameters": expected["parameters"]
            | {
                name: value
                for name, value in corrected["parameters"].items()
                if name in P11_REFITTED_PARAMETERS
            },
            "iterations": corrected["iterations"],
        }
    if "error_type" in corrected:
        return expected
    # The temperature, rho and Hall outputs retain their P8 evidence.
    return expected | {
        "result": [expected["result"][0], corrected["result"][1], *expected["result"][2:]]
    }


P14_PRIOR_FIXTURES = ("p2.json", "p3.json", "p4.json", "p5.json", "p8.json", "p11.json", "p13.json")


def affected_by_p14(scattering: str | None, call: dict[str, Any]) -> bool:
    return scattering != "acPhDis" and call["function"] != "get_parabolic_band"


@cache
def p14_document() -> dict[str, Any]:
    return json.loads((GOLDEN.parent / "physics" / "p14.json").read_text())


def current_regression_expected(
    identifier: str, scattering: str | None, call: dict[str, Any]
) -> Any:
    if affected_by_p14(scattering, call):
        return p14_document()["results"][p8_key(identifier, call)]
    return regression_expected(identifier, scattering, call)


def p8_key(identifier: str, call: dict[str, Any]) -> str:
    # A graph can call the same function repeatedly with different band parameters.
    inputs = json.dumps([call["args"], call["kwargs"]], sort_keys=True).encode()
    return identifier + "-" + hashlib.sha256(inputs).hexdigest()[:16]


def assert_recorded_replay(
    identifier: str,
    mode: str,
    scattering: str | None,
    call: dict[str, Any],
    *,
    expected: Any = None,
) -> None:
    """Compare original inputs with a model replay baseline, including failures."""
    if expected is None:
        expected = regression_expected(identifier, scattering, call)
    if call["function"].endswith("_fit"):
        result = replay_fit(mode, call)
        assert result.status == expected["status"]
        assert result.message == expected["message"]
        assert_fit_iterations(identifier, mode, scattering, result, expected["iterations"])
        assert result.parameters.keys() == expected["parameters"].keys()
        if result.status == "converged":
            expected_values = [
                expected["parameters"][name] for name in FIT_RESULT_NAMES[call["function"]]
            ]
            named_case = assert_named_fit_case(
                identifier, mode, scattering, call, result, expected_values
            )
        else:
            named_case = False
        if not named_case:
            assert result.parameters == pytest.approx(
                expected["parameters"], rel=FIT_TOLERANCE, abs=1e-9
            )
        else:
            # Parameters outside the recorded fitted vector (such as band_mass)
            # retain their original P8 comparison contract.
            for name in result.parameters.keys() - FIT_RESULT_NAMES[call["function"]]:
                assert result.parameters[name] == pytest.approx(
                    expected["parameters"][name], rel=FIT_TOLERANCE, abs=1e-9
                )
    elif "error_type" in expected:
        with pytest.raises(ValueError) as caught:
            replay(mode, scattering, call)
        assert type(caught.value).__name__ == expected["error_type"]
        assert str(caught.value) == expected["error"]
    else:
        assert_close(replay(mode, scattering, call), expected["result"], CURVE_TOLERANCE)


def test_p8_preserves_all_desktop_inputs_and_evidence() -> None:
    document = json.loads((GOLDEN.parent / "physics" / "p8.json").read_text())
    assert set(document["results"]) == {
        p8_key(identifier, call) for identifier, (*_, call) in zip(CALL_IDS, CALLS, strict=True)
    }
    assert set(document["desktop_sha256"]) == {f"{name}.json" for name in EXAMPLES}
    for name, sha in document["desktop_sha256"].items():
        assert hashlib.sha256((GOLDEN / name).read_bytes()).hexdigest() == sha


def test_p11_overrides_only_affected_calls_and_preserves_p8_evidence() -> None:
    document = json.loads((GOLDEN.parent / "physics" / "p11.json").read_text())
    assert set(document["affected_functions"]) == P11_FUNCTIONS
    assert set(document["results"]) == {
        p8_key(identifier, call)
        for identifier, (_, _, scattering, _, call) in zip(CALL_IDS, CALLS, strict=True)
        if affected_by_p11(scattering, call)
    }
    p8_path = GOLDEN.parent / "physics" / "p8.json"
    assert hashlib.sha256(p8_path.read_bytes()).hexdigest() == document["p8_sha256"]
    for key, corrected in document["results"].items():
        previous = p8_results()[key]
        if "parameters" in corrected:
            assert corrected["status"] == previous["status"]
            assert corrected["message"] == previous["message"]
            assert corrected["parameters"].keys() == previous["parameters"].keys()
            for name in corrected["parameters"].keys() - P11_REFITTED_PARAMETERS:
                assert corrected["parameters"][name] == previous["parameters"][name]
        elif "error_type" in corrected:
            assert corrected == previous
        else:
            assert len(corrected["result"]) == len(previous["result"])
            # The generated record must agree with the old evidence on all fields
            # omitted from the P11 overlay, including nonfinite curve entries.
            assert_close(
                [corrected["result"][0], *corrected["result"][2:]],
                [previous["result"][0], *previous["result"][2:]],
                CURVE_TOLERANCE,
            )


def test_p13_preserves_prior_evidence_and_records_only_branch_constrained_fits() -> None:
    document = json.loads((GOLDEN.parent / "physics" / "p13.json").read_text())
    assert document["core_version"] == "0.1.4"
    assert set(document["affected_functions"]) == P13_FUNCTIONS
    assert set(document["prior_sha256"]) == {"p8.json", "p11.json"}
    for name, sha in document["prior_sha256"].items():
        assert hashlib.sha256((GOLDEN.parent / "physics" / name).read_bytes()).hexdigest() == sha
    assert set(document["results"]) == {
        p8_key(identifier, call)
        for identifier, (*_, call) in zip(CALL_IDS, CALLS, strict=True)
        if call["function"] in P13_FUNCTIONS
    }
    for identifier, (_, mode, _, _, call) in zip(CALL_IDS, CALLS, strict=True):
        if call["function"] not in P13_FUNCTIONS:
            continue
        corrected = document["results"][p8_key(identifier, call)]
        request = fit_request("dpb_s_rho_rh" if mode == "d1" else mode, call)
        assert corrected["parameters"].keys() == request.start.keys()
        assert corrected["parameters"]["m_eff"] * request.start["m_eff"] > 0
        if corrected["status"] == "failed":
            assert corrected["parameters"] == request.start
            assert corrected["message"]


def test_p14_preserves_prior_evidence_and_covers_affected_calls() -> None:
    document = p14_document()
    assert set(document["prior_sha256"]) == set(P14_PRIOR_FIXTURES)
    assert set(document["desktop_sha256"]) == {f"{name}.json" for name in EXAMPLES}
    for directory, hashes in (
        (GOLDEN, document["desktop_sha256"]),
        (GOLDEN.parent / "physics", document["prior_sha256"]),
    ):
        for name, sha in hashes.items():
            assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == sha

    affected = {
        p8_key(identifier, call): (identifier, scattering, call)
        for identifier, (_, _, scattering, _, call) in zip(CALL_IDS, CALLS, strict=True)
        if affected_by_p14(scattering, call)
    }
    assert set(document["results"]) == affected.keys()
    assert set(document["affected_functions"]) == {
        call["function"] for _, _, call in affected.values()
    }
    for key, current in document["results"].items():
        previous = regression_expected(*affected[key])
        if previous.get("status") == "failed":
            assert current == previous
        elif "result" in current and "result" in previous:
            assert current["result"][0] == previous["result"][0]


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
        algorithm="legacy-sequential-v1",
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


@cache
def _recorded_fit(mode: str, serialized_call: str) -> FitResult:
    # Multiple assertions inspect each deterministic replay; execute that fit once.
    fit_mode = "dpb_s_rho_rh" if mode == "d1" else mode
    model = default_registry.get(fit_mode.partition("_")[0])
    return model.fit(fit_request(fit_mode, json.loads(serialized_call)))


def replay_fit(mode: str, call: dict[str, Any]) -> FitResult:
    return copy.deepcopy(_recorded_fit(mode, json.dumps(call, sort_keys=True)))


def replay(mode: str, scattering: str | None, call: dict[str, Any]) -> Any:
    """Run a recorded desktop call through the model interface, and return it in recorded order."""
    function = call["function"]
    if function == "get_parabolic_band":
        return list(parabolic_band(*call["args"]))
    if function.endswith("_fit"):
        result = replay_fit(mode, call)
        assert result.status == "converged"
        return [result.parameters[name] for name in FIT_RESULT_NAMES[function]]
    fit_mode = "dpb_s_rho_rh" if mode == "d1" else mode
    model = default_registry.get(fit_mode.partition("_")[0])
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


def assert_named_fit_case(
    identifier: str,
    mode: str,
    scattering: str | None,
    call: dict[str, Any],
    result: FitResult,
    expected: Any,
) -> bool:
    """Apply the existing machine-dependent fit policies to either reference source."""
    values = [result.parameters[name] for name in FIT_RESULT_NAMES[call["function"]]]
    if identifier.startswith("02_SiP-") and (mode, scattering) in UNSTABLE_02:
        recorded = list(flat(expected))
        assert len(values) == len(recorded)
        assert all(math.isfinite(value) for value in values[:3])
        assert "collapsed_m_eff" in result.known_issues
        assert abs(values[0]) < COLLAPSED_M_EFF
        assert_close(values[1:3], recorded[1:3], FIT_TOLERANCE)
        bounds = bounds_received(call["function"], call["args"])
        for value, (lower, upper) in zip(values[:3], bounds[:3], strict=True):
            assert lower <= value <= upper
    elif identifier.startswith("01_Fe2VAl09Si01-") and mode == "d1":
        try:
            recorded = list(flat(expected))
            if scattering == "dis" and abs(recorded[0]) < COLLAPSED_M_EFF:
                # Owner-approved unsupported-case contract: Mac and Linux
                # disagree in scattering AND rho, so neither is a numeric oracle.
                # Preserve all other comparisons and expose the unreliable state.
                # The collapsed mass is about 1e-10, where the solver stops by
                # rounding: 9.995e-11 on a Mac, 9.89e-11 on some Linux runners. It
                # is checked as collapsed and at its bound below, not by value.
                names = FIT_RESULT_NAMES[call["function"]]
                stable = [
                    index for index, name in enumerate(names) if name not in {"F", "G", "m_eff"}
                ]
                assert_close(
                    [values[index] for index in stable],
                    [recorded[index] for index in stable],
                    D1_01_TOLERANCE,
                )
                assert all(math.isfinite(value) for value in values)
                assert 0 < result.parameters["m_eff"] < COLLAPSED_M_EFF
                assert "collapsed_m_eff" in result.known_issues
                assert "hall_dis_no_reference" in result.known_issues
                assert "m_eff" in result.at_bounds
                bounds = bounds_received(call["function"], call["args"])
                for value, (lower, upper) in zip(values, bounds, strict=True):
                    assert lower <= value <= upper
            else:
                assert_close(values, expected, D1_01_TOLERANCE)
        except AssertionError as error:
            error.add_note(f"D1 fitted parameters: {dict(result.parameters)!r}")
            raise
    elif identifier.startswith("02_SiP-") and mode == "spb_s":
        assert_close(values, expected, SPB_S_02_TOLERANCE)
    else:
        return False
    return True


def assert_fit_iterations(
    identifier: str,
    mode: str,
    scattering: str | None,
    result: FitResult,
    expected: int | None,
) -> None:
    if result.status == "converged" and (
        (identifier.startswith("02_SiP-") and (mode, scattering) in UNSTABLE_02)
        or (
            identifier.startswith("01_Fe2VAl09Si01-")
            and mode == "d1"
            and scattering == "dis"
            and 0 < result.parameters.get("m_eff", math.inf) < COLLAPSED_M_EFF
            and "collapsed_m_eff" in result.known_issues
            and "m_eff" in result.at_bounds
        )
    ):
        fit_mode = "dpb_s_rho_rh" if mode == "d1" else mode
        description = default_registry.get("dpb").describe().fit_mode(fit_mode)
        if description.iterative:
            assert type(result.iterations) is int
            assert description.max_iterations is not None
            assert 1 <= result.iterations <= description.max_iterations
        else:
            assert result.iterations is None
    else:
        assert result.iterations == expected


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(
    ("example", "mode", "scattering", "source", "call"),
    [case for case in CALLS if case[2] != "acPhDis"],
    ids=[
        identifier for identifier, case in zip(CALL_IDS, CALLS, strict=True) if case[2] != "acPhDis"
    ],
)
def test_replay_matches_current_expectations(
    example: str, mode: str, scattering: str | None, source: str, call: dict[str, Any]
) -> None:
    identifier = f"{example}-{mode}-{scattering}-{source}-{call['function']}"
    expected = current_regression_expected(identifier, scattering, call)
    assert_recorded_replay(identifier, mode, scattering, call, expected=expected)
    if call["function"] == "get_parabolic_band":
        assert_close(replay(mode, scattering, call), call["result"], CURVE_TOLERANCE)


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
    # Branch-constrained fits can also exhaust their existing evaluation budget.
    with contextlib.suppress(ValueError, RuntimeError):
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
    # signed physical mass and bounds stay on the valence-band branch.
    document = json.loads((GOLDEN / "03_AWI32_SI.json").read_text(encoding="utf-8"))
    data = first_call(document, "dpb_see_res_hall_fit")["args"][:6]
    start = first_call(document, "spb_see_res_fit")["args"][5:9]
    args, kwargs = core_arguments(
        "spb_see_res_hall_fit", [*data, *start, [-1.5], ([-10.0], [-0.1]), scatter_type], {}
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


@pytest.mark.parametrize(
    ("energy", "accepted"),
    [(3.7588615470073488, True), (3.758784715324298 * 1.001, False)],
)
def test_p8_spb_sip_uses_the_existing_cross_platform_fit_contract(
    monkeypatch: pytest.MonkeyPatch, energy: float, accepted: bool
) -> None:
    identifier = "02_SiP-spb_s-None-thread-spb_see_fit"
    call = CALLS[CALL_IDS.index(identifier)][-1]
    expected = p8_results()[p8_key(identifier, call)]
    result = FitResult(
        expected["parameters"] | {"fermi_energy": energy},
        "converged",
        iterations=expected["iterations"],
        message=expected["message"],
    )
    monkeypatch.setattr(f"{__name__}.replay_fit", lambda *args: result)
    if accepted:
        assert_recorded_replay(identifier, "spb_s", None, call)
    else:
        with pytest.raises(AssertionError):
            assert_recorded_replay(identifier, "spb_s", None, call)


@pytest.mark.parametrize(
    "change", ["allowed", "mass", "gap", "fermi", "warning", "status", "message"]
)
def test_p8_d19_keeps_the_existing_physical_and_failure_checks(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    identifier = "02_SiP-dpb_s_rho-acPh-thread-dpb_see_res_fit"
    call = CALLS[CALL_IDS.index(identifier)][-1]
    expected = p8_results()[p8_key(identifier, call)]
    parameters = dict(expected["parameters"])
    # D19 already permits machine-dependent scattering after the mass collapses.
    parameters["A"] = 40000.0
    if change == "mass":
        parameters["m_eff"] = COLLAPSED_M_EFF
    elif change == "gap":
        parameters["band_gap"] *= 1.001
    elif change == "fermi":
        parameters["fermi_energy"] *= 1.001
    result = FitResult(
        parameters,
        "failed" if change == "status" else "converged",
        iterations=1,
        message="unexpected failure" if change == "message" else expected["message"],
        known_issues=() if change == "warning" else ("collapsed_m_eff",),
    )
    monkeypatch.setattr(f"{__name__}.replay_fit", lambda *args: result)
    if change == "allowed":
        assert_recorded_replay(identifier, "dpb_s_rho", "acPh", call, expected=expected)
    else:
        with pytest.raises(AssertionError):
            assert_recorded_replay(identifier, "dpb_s_rho", "acPh", call, expected=expected)


@pytest.mark.parametrize("iterations", [0, 1, 1000, 1001, None, 1.5])
def test_d19_iterations_stay_within_the_existing_mode_budget(iterations: Any) -> None:
    result = FitResult({}, "converged", iterations=iterations)
    if type(iterations) is int and 1 <= iterations <= 1000:
        assert_fit_iterations("02_SiP-dpb_s_rho-acPh-thread", "dpb_s_rho", "acPh", result, 3)
    else:
        with pytest.raises(AssertionError):
            assert_fit_iterations("02_SiP-dpb_s_rho-acPh-thread", "dpb_s_rho", "acPh", result, 3)


def test_stable_iterations_remain_exact_and_noniterative_d19_remains_none() -> None:
    with pytest.raises(AssertionError):
        assert_fit_iterations(
            "01_Fe2VAl09Si01-dpb_s_rho-acPh-thread",
            "dpb_s_rho",
            "acPh",
            FitResult({}, "converged", iterations=2),
            3,
        )
    with pytest.raises(AssertionError):
        assert_fit_iterations(
            "02_SiP-dpb_s-None-thread",
            "dpb_s",
            None,
            FitResult({}, "converged", iterations=1),
            None,
        )


@pytest.mark.parametrize("iterations", [0, 1, 4, 5, 20, 21, 1000, None, 1.5])
def test_collapsed_d1_iterations_respect_the_existing_budget(iterations: Any) -> None:
    result = FitResult(
        {"m_eff": 1e-10},
        "converged",
        iterations=iterations,
        at_bounds=("m_eff",),
        known_issues=("collapsed_m_eff", "hall_dis_no_reference"),
    )
    budget = default_registry.get("dpb").describe().fit_mode("dpb_s_rho_rh").max_iterations
    assert budget is not None
    if type(iterations) is int and 1 <= iterations <= budget:
        assert_fit_iterations("01_Fe2VAl09Si01-d1-dis-thread", "d1", "dis", result, 4)
    else:
        with pytest.raises(AssertionError):
            assert_fit_iterations("01_Fe2VAl09Si01-d1-dis-thread", "d1", "dis", result, 4)


@pytest.mark.parametrize("missing", ["collapse", "reference", "bound"])
def test_collapsed_d1_requires_its_diagnostics(missing: str) -> None:
    identifier = "01_Fe2VAl09Si01-d1-dis-thread-dpb_see_res_hall_fit"
    call = CALLS[CALL_IDS.index(identifier)][-1]
    expected = p13_results()[p8_key(identifier, call)]
    result = FitResult(
        expected["parameters"],
        "converged",
        iterations=5,
        at_bounds=() if missing == "bound" else ("m_eff",),
        known_issues=tuple(
            flag
            for flag in ("collapsed_m_eff", "hall_dis_no_reference")
            if flag
            != {"collapse": "collapsed_m_eff", "reference": "hall_dis_no_reference"}.get(missing)
        ),
    )
    with pytest.raises(AssertionError):
        assert_named_fit_case(
            identifier,
            "d1",
            "dis",
            call,
            result,
            [expected["parameters"][name] for name in FIT_RESULT_NAMES[call["function"]]],
        )


@pytest.mark.parametrize(
    "change",
    [
        "allowed",
        "mass",
        "gap",
        "fermi",
        "inactive",
        "F_nan",
        "F_bound",
        "G_bound",
        "status",
        "message",
    ],
)
def test_collapsed_d1_diagnostic_contract_preserves_its_remaining_checks(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    identifier = "01_Fe2VAl09Si01-d1-dis-thread-dpb_see_res_hall_fit"
    call = CALLS[CALL_IDS.index(identifier)][-1]
    expected = p13_results()[p8_key(identifier, call)]
    # Complete endpoint from Linux CI run 43693830497. Its rho differs from
    # the Mac capture; the owner approved diagnostic, not numeric, compatibility.
    parameters = expected["parameters"] | {
        "m_eff": 9.990967570731526e-11,
        "band_gap": -525.9005993887968,
        "fermi_energy": -165.18934125746262,
        "F": 7.99175119920054e-08,
        "G": 1.0005501718892844,
    }
    if change == "mass":
        parameters["m_eff"] = -parameters["m_eff"]
    elif change == "gap":
        parameters["band_gap"] *= 1.01
    elif change == "fermi":
        parameters["fermi_energy"] *= 1.01
    elif change == "inactive":
        parameters["A"] *= 2
    elif change == "F_nan":
        parameters["F"] = float("nan")
    elif change == "F_bound":
        parameters["F"] = -1.0
    elif change == "G_bound":
        parameters["G"] = 201.0
    result = FitResult(
        parameters,
        "failed" if change == "status" else "converged",
        iterations=5,
        message="unexpected failure" if change == "message" else None,
        at_bounds=("m_eff", "F", "m1"),
        known_issues=("collapsed_m_eff", "hall_dis_no_reference"),
    )
    monkeypatch.setattr(f"{__name__}.replay_fit", lambda *args: result)
    if change == "allowed":
        assert_recorded_replay(identifier, "d1", "dis", call)
    else:
        with pytest.raises(AssertionError):
            assert_recorded_replay(identifier, "d1", "dis", call)
