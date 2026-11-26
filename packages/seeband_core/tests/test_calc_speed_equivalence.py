"""A15: faster curves and fits give the same numbers to the last bit.

Two changes make them faster: `fdint` calls `fdint_robust` directly for one value instead of
through `np.vectorize`, and μ(T) is solved once for each temperature array and parameters within
one curve or fit. Each test computes with both off, as before, and with both on, and compares every
value's bytes.
"""

import contextlib
import itertools
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core import band_models, math_module
from seeband_core.data_parser import parse_table
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest, FitRequest
from seeband_core.model_scales import default_start

EXAMPLE = Path(__file__).parent / "fixtures" / "examples" / "01_Fe2VAl09Si01"


@contextlib.contextmanager
def _as_before(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The calculations as they were: every Fermi integral through np.vectorize, no reuse."""
    with monkeypatch.context() as patch:
        patch.setattr(math_module, "fdint", math_module.fdint_vec)
        patch.setattr(band_models, "reuse_chemical_potential", contextlib.nullcontext)
        yield


def _bytes(value: Any) -> Any:
    if isinstance(value, dict):
        return {name: _bytes(item) for name, item in value.items()}
    array = np.asarray(value, dtype=float)
    return (array.shape, array.tobytes())


def _outcome(call: Any) -> Any:
    """What a call gives: its values to the bit, or the kind and text of its error."""
    try:
        result = call()
    except Exception as error:  # noqa: BLE001 - both paths must fail alike
        return ("error", type(error).__name__, str(error))
    return result


def _curve_bytes(result: Any) -> Any:
    if isinstance(result, tuple) and result and result[0] == "error":
        return result
    return (
        _bytes(result.temperature_k),
        _bytes(dict(result.curves)),
        result.known_issues,
    )


# Parameters around each mode's defaults: the sign of the mass, a Fermi energy inside and outside a
# band, and a second band's degeneracy, so that each branch of the integrals and the solve runs.
_VARIATIONS: list[dict[str, float]] = [
    {},
    {"fermi_energy": 300.0},
    {"fermi_energy": -50.0},
    {"m_eff": -1.5},
    {"band_mass": -1.5},
    {"band_gap": 200.0, "fermi_energy": 150.0},
]


def _variations(fit_mode: Any) -> list[int]:
    """The variations that give the mode a distinct input. Some affect another model only."""
    names = {spec.name for spec in fit_mode.parameters}
    variations = []
    seen = set()
    for index, values in enumerate(_VARIATIONS):
        parameters = default_start(fit_mode) | {
            name: value for name, value in values.items() if name in names
        }
        effective = tuple(sorted(parameters.items()))
        if effective not in seen:
            seen.add(effective)
            variations.append(index)
    return variations


def _cases() -> list[tuple[str, str, str | None, str, int, float]]:
    cases = []
    for description in registry.descriptions():
        for fit_mode in description.fit_modes:
            variations = _variations(fit_mode)
            for scattering in fit_mode.scattering or (None,):
                for kind in fit_mode.curve_kinds:
                    for variation, degeneracy in itertools.product(variations, (1.0, 3.0)):
                        if degeneracy != 1.0 and fit_mode.degeneracy is None:
                            continue
                        cases.append(
                            (description.id, fit_mode.id, scattering, kind, variation, degeneracy)
                        )
    return cases


CASES = _cases()


def test_the_comparison_covers_every_mode_scattering_and_kind() -> None:
    covered = {(model, mode, scattering, kind) for model, mode, scattering, kind, *_ in CASES}
    expected = {
        (description.id, fit_mode.id, scattering, kind)
        for description in registry.descriptions()
        for fit_mode in description.fit_modes
        for scattering in fit_mode.scattering or (None,)
        for kind in fit_mode.curve_kinds
    }
    assert covered == expected


def test_each_variation_that_touches_a_mode_changes_its_input() -> None:
    # Dropping duplicates must not drop a branch: if a default moves onto a variation's value, the
    # variation stops testing anything, and this fails so that the variations can be updated.
    for description in registry.descriptions():
        for fit_mode in description.fit_modes:
            names = {spec.name for spec in fit_mode.parameters}
            touching = [
                index
                for index, values in enumerate(_VARIATIONS)
                if index == 0 or names & values.keys()
            ]
            assert _variations(fit_mode) == touching, fit_mode.id


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(
    ("model_id", "mode_id", "scattering", "kind", "variation", "degeneracy"), CASES
)
def test_a_curve_is_the_same_to_the_bit(
    monkeypatch: pytest.MonkeyPatch,
    model_id: str,
    mode_id: str,
    scattering: str | None,
    kind: str,
    variation: int,
    degeneracy: float,
) -> None:
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(mode_id)
    names = {spec.name for spec in fit_mode.parameters}
    parameters = default_start(fit_mode) | {
        name: value for name, value in _VARIATIONS[variation].items() if name in names
    }
    request = CurveRequest(
        mode_id,
        parameters,
        50.0,
        800.0,
        60,
        scattering,
        kind,  # type: ignore[arg-type]
        band_2_degeneracy=degeneracy,
    )

    with _as_before(monkeypatch):
        before = _curve_bytes(_outcome(lambda: model.calculate(request)))
    now = _curve_bytes(_outcome(lambda: model.calculate(request)))

    assert now == before


def _fit_request(
    mode_id: str, scattering: str | None, algorithm: str = "legacy-sequential-v1"
) -> tuple[Any, FitRequest]:
    model = registry.get(mode_id.partition("_")[0])
    fit_mode = model.describe().fit_mode(mode_id)
    measurements = {
        quantity: parse_table(Path(f"{EXAMPLE}_{suffix}.txt").read_text(), quantity).measurements[
            quantity
        ]
        for quantity, suffix in (("seebeck", "see"), ("resistivity", "rho"))
        if quantity in fit_mode.quantities
    }
    return model, FitRequest(
        mode_id,
        measurements,
        default_start(fit_mode),
        scattering=scattering,
        algorithm=algorithm,  # type: ignore[arg-type]
    )


def _fit_outcome(model: Any, request: FitRequest) -> Any:
    """Everything a fit gives: its result, each iteration, its warnings and its fitted curve."""
    iterations: list[Any] = []

    def fit() -> Any:
        result = model.fit(request, lambda *update: iterations.append(update))
        curve = _outcome(
            lambda: model.calculate(
                CurveRequest(
                    request.fit_mode,
                    dict(result.parameters),
                    50.0,
                    800.0,
                    40,
                    request.scattering,
                )
            )
        )
        return (
            result.status,
            result.iterations,
            result.message,
            _bytes(dict(result.parameters)),
            _bytes(dict(result.parameter_errors)),
            sorted(result.at_bounds),
            sorted(result.held),
            _curve_bytes(curve),
            None if result.diagnostics is None else result.diagnostics.termination,
        )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        outcome = _outcome(fit)
    return (
        outcome,
        repr(iterations),
        [(warning.category.__name__, str(warning.message)) for warning in caught],
    )


# Both fit algorithms: the legacy one of the desktop, and the verified one, the default. A verified
# dpb_s_rho fit is expensive, so its full-budget failure comparison is opt-in extended coverage.
_FITS = [
    ("dpb_s", None, "legacy-sequential-v1"),
    ("dpb_s_rho", "acPh", "legacy-sequential-v1"),
    ("spb_s_rho", "acPh", "legacy-sequential-v1"),
    ("dpb_s", None, "verified-sequential-v2"),
    ("dpb_s_rho", "acPh", "verified-sequential-v2"),
    ("spb_s_rho", "acPh", "verified-sequential-v2"),
]


@pytest.mark.parametrize(
    ("mode_id", "scattering", "algorithm"),
    [fit for fit in _FITS if fit != ("dpb_s_rho", "acPh", "verified-sequential-v2")],
)
def test_a_fit_is_the_same_to_the_bit(
    monkeypatch: pytest.MonkeyPatch, mode_id: str, scattering: str | None, algorithm: str
) -> None:
    model, request = _fit_request(mode_id, scattering, algorithm)

    with _as_before(monkeypatch):
        before = _fit_outcome(model, request)
    now = _fit_outcome(model, request)

    assert now == before


@pytest.mark.parametrize(
    ("mode_id", "scattering", "algorithm"),
    [
        pytest.param(*fit, marks=pytest.mark.extended)
        if fit == ("dpb_s_rho", "acPh", "verified-sequential-v2")
        else fit
        for fit in _FITS
    ],
)
def test_a_fit_whose_solves_fail_on_the_way_is_the_same_to_the_bit(
    monkeypatch: pytest.MonkeyPatch, mode_id: str, scattering: str | None, algorithm: str
) -> None:
    """Every fourth set of parameters the fit tries has no root.

    The legacy fit goes on past them and converges. The verified fit can reject invalid trial
    points or return a checked failure depending on where the injected error falls. The sets are
    counted in the order they first come, so the same ones fail with and without reuse.
    """
    solve = math_module._solve_chemical_potential
    seen: dict[tuple[bytes, ...], int] = {}
    failures = 0

    def failing(temp_array: Any, mass: Any, fermi_energy: Any, *rest: Any) -> Any:
        nonlocal failures
        key = tuple(np.float64(value).tobytes() for value in (mass, fermi_energy, *rest))
        if seen.setdefault(key, len(seen)) % 4 == 3:
            failures += 1
            raise math_module.NoFiniteChemicalPotentialError(None, "made to fail by the test")
        return solve(temp_array, mass, fermi_energy, *rest)

    monkeypatch.setattr(math_module, "_solve_chemical_potential", failing)
    model, request = _fit_request(mode_id, scattering, algorithm)

    with _as_before(monkeypatch):
        before = _fit_outcome(model, request)
    failed_before, failures = failures, 0
    seen.clear()
    now = _fit_outcome(model, request)

    assert failed_before > 0
    assert failures > 0
    if algorithm == "legacy-sequential-v1":
        assert before[0][0] == "converged"
    elif mode_id == "dpb_s_rho" and scattering == "acPh":
        assert before[0][0] == "iteration_limit"
        assert before[0][-1] == "evaluation_budget"
    assert now == before


def test_reuse_keeps_nothing_after_a_call() -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s_rho_rh")
    model.calculate(CurveRequest("dpb_s_rho_rh", default_start(fit_mode), 50.0, 800.0, 20, "acPh"))
    assert math_module._REUSED_ROOTS.get() is None


def test_one_curve_solves_each_chemical_potential_once(monkeypatch: pytest.MonkeyPatch) -> None:
    solves = 0
    solve = math_module._solve_chemical_potential

    def counted(*args: Any) -> Any:
        nonlocal solves
        solves += 1
        return solve(*args)

    monkeypatch.setattr(math_module, "_solve_chemical_potential", counted)
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s_rho_rh")
    model.calculate(CurveRequest("dpb_s_rho_rh", default_start(fit_mode), 50.0, 800.0, 20, "acPh"))

    # S, rho and R_H share one μ(T), which was solved three times before.
    assert solves == 1


def test_reused_roots_are_copies_that_a_caller_cannot_change() -> None:
    temperatures = np.array([100.0, 300.0])
    with math_module.reuse_chemical_potential():
        first = math_module.dpb_chemPot_vs_temp(temperatures, 1000.0, 1.0, -100.0, 1.0)
        first[:] = 0.0
        second = math_module.dpb_chemPot_vs_temp(temperatures, 1000.0, 1.0, -100.0, 1.0)
    assert np.all(second != 0.0)


def test_negative_zero_is_not_taken_for_zero() -> None:
    with math_module.reuse_chemical_potential():
        math_module.dpb_chemPot_vs_temp(np.array([300.0]), 1000.0, 1.0, 0.0, 1.0)
        reused = math_module._REUSED_ROOTS.get()
        assert reused is not None
        math_module.dpb_chemPot_vs_temp(np.array([300.0]), 1000.0, 1.0, -0.0, 1.0)
        assert len(reused) == 2


def test_a_failed_solve_is_solved_again() -> None:
    solves = 0
    solve = math_module._solve_chemical_potential

    def counted(*args: Any) -> Any:
        nonlocal solves
        solves += 1
        return solve(*args)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(math_module, "_solve_chemical_potential", counted)
        with math_module.reuse_chemical_potential():
            for _ in range(2):
                with pytest.raises(math_module.ChemicalPotentialError):
                    math_module.spb_chemPot_diagnostics(np.array([300.0]), 1.0, -100.0)
    assert solves == 2


def test_a_float32_is_not_taken_for_its_float64() -> None:
    with math_module.reuse_chemical_potential():
        math_module.spb_chemPot_diagnostics(np.array([300.0]), 1.0, np.float64(0.1))
        reused = math_module._REUSED_ROOTS.get()
        assert reused is not None
        math_module.spb_chemPot_diagnostics(np.array([300.0]), 1.0, np.float32(0.1))
        assert len(reused) == 2


def test_a_reused_root_holds_no_status_strings() -> None:
    with math_module.reuse_chemical_potential():
        result = math_module.spb_chemPot_diagnostics(np.array([100.0, 300.0]), 1.0, 50.0)
        reused = math_module._REUSED_ROOTS.get()
        assert reused is not None
        (kept,) = reused.values()
    assert all(array.dtype == np.float64 for array in kept)
    assert list(result.status) == ["converged", "converged"]


def test_a_float_and_its_float64_share_roots() -> None:
    with math_module.reuse_chemical_potential():
        math_module.spb_chemPot_diagnostics(np.array([300.0]), 1.0, 0.1)
        reused = math_module._REUSED_ROOTS.get()
        assert reused is not None
        math_module.spb_chemPot_diagnostics(np.array([300.0]), np.float64(1.0), np.float64(0.1))
        assert len(reused) == 1
