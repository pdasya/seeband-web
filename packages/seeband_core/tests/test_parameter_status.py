"""R7: how a fit found each parameter, from the signals it has, and no green "fitted" for all."""

import logging

import numpy as np
import pytest
from seeband_core.demo_dataset import load_demo_dataset
from seeband_core.model_catalog import registry
from seeband_core.model_interface import Bounds, CurveRequest, FitRequest, FitStopped
from seeband_core.model_scales import default_start
from seeband_core.parameter_status import DID_NOT_MOVE_TOLERANCE, parameter_statuses

DEMO = load_demo_dataset().measurements
ALGORITHMS = ("legacy-sequential-v1", "verified-sequential-v2")


def _fit(model_id: str, mode_id: str, **fields: object) -> object:
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(mode_id)
    start = fields.pop("start", default_start(fit_mode))
    on_iteration = fields.pop("on_iteration", None)
    request = FitRequest(
        mode_id,
        {quantity: DEMO[quantity] for quantity in fit_mode.quantities},
        start,  # type: ignore[arg-type]
        **fields,  # type: ignore[arg-type]
    )
    return model.fit(request, on_iteration)  # type: ignore[arg-type]


@pytest.mark.parametrize("mode_id", ["dpb_s", "dpb_s_rho", "dpb_s_rho_rh"])
def test_dpb_curves_do_not_depend_on_a_fermi_energy_inside_the_gap(mode_id: str) -> None:
    """The reason for `not_determined` of E_F there: both bands are empty at 0 K for each value."""
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode(mode_id)
    start = default_start(fit_mode) | {"m_eff": 1.2, "band_gap": 800.0}

    def curves(fermi_energy: float) -> dict[str, bytes]:
        result = model.calculate(
            CurveRequest(
                mode_id,
                start | {"fermi_energy": fermi_energy},
                100.0,
                800.0,
                12,
                fit_mode.default_scattering,
            )
        )
        return {name: np.asarray(values).tobytes() for name, values in result.curves.items()}

    assert curves(50.0) == curves(400.0) == curves(790.0)
    assert curves(400.0) != curves(810.0)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(("mode_id", "scattering"), [("dpb_s", None), ("dpb_s_rho", "acPh")])
def test_a_fermi_energy_inside_the_gap_is_not_determined(
    mode_id: str, scattering: str | None, algorithm: str
) -> None:
    """The review's s13 cases: E_F in the gap with m_eff > 0 has no effect on the data.

    The legacy fit ends with E_F where it started, which says nothing about it. The verified fit
    finds no derivative to verify and fails, so it assesses E_F not at all. Neither calls it
    estimated.
    """
    fit_mode = registry.get("dpb").describe().fit_mode(mode_id)
    start = default_start(fit_mode) | {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 400.0}
    held = frozenset(name for name in ("m_eff", "band_gap", "A", "B") if name in start)

    result = _fit(
        "dpb", mode_id, start=start, scattering=scattering, algorithm=algorithm, held=held
    )

    status = result.parameter_status["fermi_energy"]  # type: ignore[attr-defined]
    if algorithm == "legacy-sequential-v1":
        assert result.status != "failed"  # type: ignore[attr-defined]
        assert 0 < result.parameters["fermi_energy"] < 800.0  # type: ignore[attr-defined]
        assert status == "not_determined"
    else:
        assert result.status == "failed"  # type: ignore[attr-defined]
        assert status == "not_assessed"


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_a_stopped_fit_marks_a_parameter_at_its_bound(algorithm: str) -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s_rho")
    start = default_start(fit_mode)

    def stop(_: object) -> None:
        raise FitStopped

    result = _fit(
        "dpb",
        "dpb_s_rho",
        start=start,
        bounds={"B": Bounds(start["B"] * 0.999, start["B"] * 1.0001)},
        scattering="acPh",
        algorithm=algorithm,
        on_iteration=stop,
    )

    assert result.status == "stopped"  # type: ignore[attr-defined]
    assert "B" in result.at_bounds  # type: ignore[attr-defined]
    assert result.parameter_status["B"] == "at_bound"  # type: ignore[attr-defined]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_held_fixed_and_fitted_parameters_each_have_a_status(algorithm: str) -> None:
    result = _fit("dpb", "dpb_s_rho", scattering="acPh", algorithm=algorithm, held={"B"})
    statuses = result.parameter_status  # type: ignore[attr-defined]
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s_rho")

    assert set(statuses) == set(result.parameters)  # type: ignore[attr-defined]
    assert statuses["B"] == "held"
    for spec in fit_mode.parameters:
        if spec.role == "fixed" or "acPh" not in (spec.scattering or ("acPh",)):
            assert statuses[spec.name] == "fixed"
    assert statuses["m_eff"] == "estimated"


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_a_failed_fit_assesses_no_parameter(
    algorithm: str, caplog: pytest.LogCaptureFixture
) -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s")
    # The start band mass has the wrong sign for E_F above both bands, so no root exists.
    start = default_start(fit_mode) | {"m_eff": -1.0, "band_gap": 100.0, "fermi_energy": 500.0}

    with caplog.at_level(logging.CRITICAL):
        result = _fit("dpb", "dpb_s", start=start, algorithm=algorithm)

    assert result.status == "failed"  # type: ignore[attr-defined]
    fitted = {spec.name for spec in fit_mode.parameters if spec.role == "fitted"}
    assert {
        name: status
        for name, status in result.parameter_status.items()  # type: ignore[attr-defined]
        if name in fitted
    } == dict.fromkeys(fitted, "not_assessed")


def test_a_stopped_hall_fit_does_not_assess_m1() -> None:
    def stop(_: object) -> None:
        raise FitStopped

    result = _fit(
        "dpb",
        "dpb_s_rho_rh",
        scattering="acPh",
        algorithm="legacy-sequential-v1",
        on_iteration=stop,
    )

    assert result.status == "stopped"  # type: ignore[attr-defined]
    assert result.parameter_status["m1"] == "not_assessed"  # type: ignore[attr-defined]


def _statuses(parameters: dict[str, float], **signals: object) -> dict[str, str]:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s")
    start = {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 900.0}
    return dict(
        parameter_statuses(
            fit_mode,
            None,
            start,
            start | parameters,
            status=signals.pop("status", "converged"),  # type: ignore[arg-type]
            held=signals.pop("held", ()),  # type: ignore[arg-type]
            at_bounds=signals.pop("at_bounds", ()),  # type: ignore[arg-type]
            undetermined=signals.pop("undetermined", ()),  # type: ignore[arg-type]
            reached=signals.pop("reached", None),  # type: ignore[arg-type]
        )
    )


def test_each_signal_gives_its_status_in_order() -> None:
    moved = {"m_eff": 1.5, "band_gap": 700.0, "fermi_energy": 950.0}
    assert _statuses(moved) == dict.fromkeys(moved, "estimated")
    assert _statuses(moved, undetermined={"m_eff"})["m_eff"] == "not_determined"
    # A bound is said first, as it may be what set the value.
    assert _statuses(moved, undetermined={"m_eff"}, at_bounds={"m_eff"})["m_eff"] == "at_bound"
    assert _statuses(moved, reached={"m_eff"})["band_gap"] == "not_assessed"
    assert _statuses(moved, status="failed")["m_eff"] == "not_assessed"
    assert _statuses(moved, held={"m_eff"})["m_eff"] == "held"


def test_a_value_that_stayed_at_its_start_did_not_move() -> None:
    within = 900.0 * (1 + DID_NOT_MOVE_TOLERANCE / 2)
    beyond = 900.0 * (1 + DID_NOT_MOVE_TOLERANCE * 2)
    assert _statuses({"fermi_energy": within})["fermi_energy"] == "did_not_move"
    assert _statuses({"fermi_energy": beyond})["fermi_energy"] == "estimated"


def test_only_a_dpb_fermi_energy_strictly_inside_the_gap_with_a_positive_mass() -> None:
    moved = {"m_eff": 1.5, "band_gap": 800.0}
    assert _statuses(moved | {"fermi_energy": 400.0})["fermi_energy"] == "not_determined"
    assert _statuses(moved | {"fermi_energy": 810.0})["fermi_energy"] == "estimated"
    assert _statuses(moved | {"fermi_energy": -5.0})["fermi_energy"] == "estimated"
    negative = {"m_eff": -1.5, "band_gap": 800.0, "fermi_energy": 400.0}
    assert _statuses(negative)["fermi_energy"] == "estimated"
