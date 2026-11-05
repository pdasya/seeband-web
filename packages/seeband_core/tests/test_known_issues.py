import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core.known_issues import ALL_MODES, KNOWN_ISSUES, active_issue_ids, issues_for_mode
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveKind, CurveRequest, FitMode, FitRequest, Measurement
from seeband_core.model_scales import default_start

DOC = Path(__file__).parents[1] / "docs" / "known-issues.md"


def fit_mode(fit_mode_id: str) -> FitMode:
    return registry.get(fit_mode_id.partition("_")[0]).describe().fit_mode(fit_mode_id)


def ids(
    fit_mode_id: str, scattering: str | None, kind: CurveKind | None = None, **kw: Any
) -> set[str]:
    parameters = kw.pop("parameters", {})
    ratio = kw.pop("ratio", 1.0)
    return set(active_issue_ids(fit_mode(fit_mode_id), scattering, parameters, ratio, kind, **kw))


def test_ids_are_unique() -> None:
    names = [issue.id for issue in KNOWN_ISSUES]
    assert len(set(names)) == len(names)


@pytest.mark.parametrize("issue", KNOWN_ISSUES, ids=lambda issue: issue.id)
def test_each_entry_is_complete_and_valid(issue: Any) -> None:
    assert re.fullmatch(r"#\d+", issue.fixed_by)
    assert issue.explanation
    assert issue.message_key == f"known_issue.{issue.id}"
    assert issue.fit_modes
    assert issue.curve_kinds or issue.affects_fit or issue.condition
    for fit_mode_id in issue.fit_modes:
        mode = fit_mode(fit_mode_id)
        assert issue in mode.known_issues
        assert set(issue.scattering) <= set(mode.scattering) or not issue.scattering
        # A kind the mode does not offer is fine for a list that spans modes, but one must offer it.
    for kind in issue.curve_kinds:
        assert any(kind in fit_mode(name).curve_kinds for name in issue.fit_modes), kind


def test_the_doc_lists_every_entry_with_its_fix() -> None:
    text = DOC.read_text(encoding="utf-8")
    for issue in KNOWN_ISSUES:
        row = next(line for line in text.splitlines() if line.startswith(f"| `{issue.id}`"))
        assert issue.severity in row
        assert issue.fixed_by in row


def test_issues_for_mode_selects_by_mode() -> None:
    names = {issue.id for issue in issues_for_mode("spb_s")}
    assert names == {"interpolation_extrapolates"}
    assert "dpb_hall_prefactor" in {issue.id for issue in issues_for_mode("dpb_s_rho_rh")}


def test_only_the_spb_hall_mode_is_disabled_and_the_table_agrees() -> None:
    path = resources.files("seeband_core") / "data" / "desktop_modes.json"
    for mode in json.loads(path.read_text("utf-8"))["modes"]:
        assert fit_mode(mode["id"]).disabled is (mode["status"] == "fails_on_desktop")
    assert [name for name in ALL_MODES if fit_mode(name).disabled] == ["spb_s_rho_rh"]


def test_the_dis_mode_that_fails_on_the_desktop_is_flagged() -> None:
    assert "hall_dis_web_bounds" in ids("dpb_s_rho_rh", "dis")
    assert "hall_dis_web_bounds" not in ids("dpb_s_rho_rh", "acPh")
    assert "hall_dis_web_bounds" not in ids("dpb_s_rho", "dis")


@pytest.mark.parametrize(
    ("mode", "scattering", "kind", "expected", "absent"),
    [
        ("dpb_s_rho_rh", "acPh", "measured", {"dpb_hall_prefactor"}, set()),
        ("dpb_s_rho_rh", "acPh", "carrier_concentration_by_band", {"dpb_hall_prefactor"}, set()),
        ("dpb_s_rho", "acPh", "measured", set(), {"dpb_hall_prefactor"}),
        ("dpb_s_rho_rh", "acPh", "chemical_potential", set(), {"dpb_hall_prefactor"}),
        ("spb_s_rho", "acPhDis", "electrical_conductivity", {"acphdis_conductivity_scale"}, set()),
        ("dpb_s_rho", "acPhDis", "thermal_conductivity", {"acphdis_conductivity_scale"}, set()),
        (
            "dpb_s_rho_rh",
            "acPhDis",
            "electrical_conductivity_by_band",
            {"acphdis_conductivity_scale"},
            set(),
        ),
        ("spb_s_rho", "acPh", "electrical_conductivity", set(), {"acphdis_conductivity_scale"}),
        ("spb_s_rho", "acPhDis", "measured", set(), {"acphdis_conductivity_scale"}),
        ("dpb_s_rho", "acPhDis", "measured", {"acphdis_band_weight"}, set()),
        ("dpb_s_rho", "acPhDis", "seebeck", {"acphdis_band_weight"}, set()),
        ("dpb_s_rho", "dis", "measured", set(), {"acphdis_band_weight"}),
        ("spb_s_rho_rh", "acPh", "measured", {"spb_hall_uses_fermi_energy"}, set()),
    ],
)
def test_curves_get_the_issues_that_apply(
    mode: str, scattering: str, kind: Any, expected: set[str], absent: set[str]
) -> None:
    found = ids(mode, scattering, kind)
    assert expected <= found
    assert not absent & found


@pytest.mark.parametrize(
    ("mode", "scattering", "expected", "absent"),
    [
        ("dpb_s_rho_rh", "acPh", {"dpb_hall_prefactor"}, {"acphdis_early_stop"}),
        (
            "dpb_s_rho",
            "acPhDis",
            {"acphdis_early_stop", "acphdis_band_weight"},
            {"dpb_hall_prefactor"},
        ),
        ("dpb_s_rho", "acPh", set(), {"acphdis_early_stop", "acphdis_conductivity_scale"}),
        ("spb_s_rho_rh", "acPh", {"spb_hall_mode_disabled"}, set()),
    ],
)
def test_fits_get_the_issues_that_apply(
    mode: str, scattering: str, expected: set[str], absent: set[str]
) -> None:
    found = ids(mode, scattering)
    assert expected <= found
    assert not absent & found


def test_conditions_are_checked() -> None:
    assert "dpb_s_degeneracy" not in ids("dpb_s", None)
    assert "dpb_s_degeneracy" in ids("dpb_s", None, ratio=2.0)
    assert "dpb_s_degeneracy" in ids("dpb_s", None, "measured", ratio=0.5)
    assert "negative_m_eff_weight" not in ids("dpb_s", None, parameters={"m_eff": 1.0})
    assert "negative_m_eff_weight" not in ids("dpb_s", None, parameters={"m_eff": 0.0})
    assert "negative_m_eff_weight" in ids("dpb_s", None, parameters={"m_eff": -1.0})
    assert "negative_m_eff_weight" in ids("dpb_s", None, "measured", parameters={"m_eff": -1.0})
    assert "negative_m_eff_weight" not in ids(
        "dpb_s", None, "chemical_potential", parameters={"m_eff": -1.0}
    )


def test_extrapolation_applies_wherever_it_is_reported() -> None:
    assert "interpolation_extrapolates" not in ids("spb_s", None)
    assert "interpolation_extrapolates" in ids("spb_s", None, extrapolated=True)
    assert "interpolation_extrapolates" in ids("dpb_s_rho", "acPh", "measured", extrapolated=True)


def synthetic(fit_mode_id: str) -> dict[Any, Measurement]:
    temperature_k = np.linspace(100.0, 800.0, 12)
    values = {"seebeck": 1e-4, "resistivity": 1e-5, "hall": 1e-7}
    return {
        quantity: Measurement(temperature_k, values[quantity] * temperature_k / 100.0)
        for quantity in fit_mode(fit_mode_id).quantities
    }


def test_results_carry_their_issues() -> None:
    model = registry.get("dpb")
    start = default_start(fit_mode("dpb_s"))
    plain = model.calculate(CurveRequest("dpb_s", start, 100, 300, 3))
    assert plain.known_issues == ()
    with_n = model.calculate(CurveRequest("dpb_s", start, 100, 300, 3, band_2_degeneracy=2.0))
    assert with_n.known_issues == ("dpb_s_degeneracy",)
    negative = model.calculate(
        CurveRequest("dpb_s", start | {"m_eff": -1.0, "band_gap": -200.0}, 100, 300, 3)
    )
    assert negative.known_issues == ("negative_m_eff_weight",)
    hall = model.calculate(
        CurveRequest("dpb_s_rho_rh", default_start(fit_mode("dpb_s_rho_rh")), 100, 300, 3, "acPh")
    )
    assert "dpb_hall_prefactor" in hall.known_issues


@pytest.mark.filterwarnings("ignore")
def test_a_fit_result_carries_its_issues_and_a_failed_one_does_not() -> None:
    model = registry.get("dpb")
    start = default_start(fit_mode("dpb_s_rho"))
    result = model.fit(FitRequest("dpb_s_rho", synthetic("dpb_s_rho"), start, scattering="acPhDis"))
    assert set(result.known_issues) == {"acphdis_band_weight", "acphdis_early_stop"}
    failed = model.fit(
        FitRequest("dpb_s_rho", synthetic("dpb_s_rho"), start | {"A": -5.0}, scattering="acPh")
    )
    assert failed.status == "failed"
    assert failed.known_issues == ()


def test_removing_an_entry_removes_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    import seeband_core.known_issues as module

    kept = tuple(issue for issue in KNOWN_ISSUES if issue.id != "dpb_hall_prefactor")
    monkeypatch.setattr(module, "KNOWN_ISSUES", kept)
    assert "dpb_hall_prefactor" not in {i.id for i in module.issues_for_mode("dpb_s_rho_rh")}
