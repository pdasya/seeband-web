import dataclasses
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core.known_issues import (
    COLLAPSED_M_EFF,
    KNOWN_ISSUES,
    active_issue_ids,
    band_diagram_issue_ids,
    issues_for_mode,
)
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveKind, CurveRequest, FitMode, FitRequest, Measurement
from seeband_core.model_scales import default_start

DOC = Path(__file__).parents[1] / "docs" / "known-issues.md"
# The public Conventions page lists them too, so that visitors see what is flagged.
CONVENTIONS = Path(__file__).parents[3] / "apps" / "site" / "src" / "pages" / "conventions.mdx"
SPB = ("spb_s", "spb_s_rho", "spb_s_rho_rh")
DPB = ("dpb_s", "dpb_s_rho", "dpb_s_rho_rh")
LOOP = ("dpb_s_rho", "dpb_s_rho_rh")
DPB_FIT_CURVES = (
    "measured",
    "seebeck",
    "seebeck_by_band",
    "electrical_conductivity",
    "electrical_conductivity_by_band",
    "thermal_conductivity",
    "lorenz_number",
)
ALL_CURVES = (*DPB_FIT_CURVES, "chemical_potential", "carrier_concentration_by_band")
# Written here so that a change of scope, severity or fix fails.
# id: severity, fixed by, modes, scattering, curve kinds, affects fit, condition.
EXPECTED: dict[str, tuple[Any, ...]] = {
    "dpb_loop_degeneracy": ("caution", "#85", LOOP, (), (), True, "degeneracy_not_one"),
    "collapsed_m_eff": ("unreliable", "#107", DPB, (), ALL_CURVES, True, "collapsed_m_eff"),
    "no_chemical_potential": (
        "unreliable",
        "#106",
        SPB,
        (),
        (
            "measured",
            "chemical_potential",
            "electrical_conductivity",
            "thermal_conductivity",
            "lorenz_number",
        ),
        True,
        "fermi_energy_outside_band",
    ),
    "hall_dis_no_reference": ("caution", "#71", ("dpb_s_rho_rh",), ("dis",), (), True, None),
    "interpolation_extrapolates": (
        "unreliable",
        "#86",
        (*SPB, *DPB),
        (),
        (),
        False,
        "interpolation_extrapolated",
    ),
}


def fit_mode(fit_mode_id: str) -> FitMode:
    return registry.get(fit_mode_id.partition("_")[0]).describe().fit_mode(fit_mode_id)


def ids(
    fit_mode_id: str, scattering: str | None, kind: CurveKind | None = None, **kw: Any
) -> set[str]:
    parameters = kw.pop("parameters", {})
    ratio = kw.pop("ratio", 1.0)
    return set(active_issue_ids(fit_mode(fit_mode_id), scattering, parameters, ratio, kind, **kw))


def test_entries_are_as_written_here() -> None:
    found = {
        issue.id: (
            issue.severity,
            issue.fixed_by,
            issue.fit_modes,
            issue.scattering,
            issue.curve_kinds,
            issue.affects_fit,
            issue.condition,
        )
        for issue in KNOWN_ISSUES
    }
    assert found == EXPECTED
    assert len(KNOWN_ISSUES) == len(EXPECTED)


@pytest.mark.parametrize("issue", KNOWN_ISSUES, ids=lambda issue: issue.id)
def test_each_entry_is_usable(issue: Any) -> None:
    assert re.fullmatch(r"#\d+", issue.fixed_by)
    assert issue.explanation
    assert issue.message_key == f"known_issue.{issue.id}"
    for fit_mode_id in issue.fit_modes:
        assert issue in fit_mode(fit_mode_id).known_issues
        assert set(issue.scattering) <= set(fit_mode(fit_mode_id).scattering)
    for kind in issue.curve_kinds:
        assert any(kind in fit_mode(name).curve_kinds for name in issue.fit_modes), kind


def test_the_doc_and_the_list_match_both_ways() -> None:
    rows = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\| `(\w+)`\s*\| (\w+)\s*\|.*\| (#\d+)\s*\|$", line)
        if match:
            rows[match.group(1)] = (match.group(2), match.group(3))
    assert rows == {issue.id: (issue.severity, issue.fixed_by) for issue in KNOWN_ISSUES}


def test_the_conventions_page_lists_each_issue_as_the_registry_does() -> None:
    if not CONVENTIONS.exists():
        pytest.skip("The site is not beside the core, as in a copy of the package alone")
    rows = {}
    for line in CONVENTIONS.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\| `(\w+)`\s*\| (\w+)\s*\|.*\| \[(#\d+)\]\([^)]*\)\s*\|$", line)
        if match:
            rows[match.group(1)] = (match.group(2), match.group(3))
    assert rows == {issue.id: (issue.severity, issue.fixed_by) for issue in KNOWN_ISSUES}


def test_a_description_serialises_with_its_keys() -> None:
    description = registry.get("dpb").describe()
    text = json.dumps(dataclasses.asdict(description), allow_nan=False)
    assert "known_issue.dpb_hall_prefactor" not in text


@pytest.mark.parametrize("name", [*SPB, *DPB])
def test_the_repaired_band_diagram_has_no_active_issues(name: str) -> None:
    assert band_diagram_issue_ids(fit_mode(name)) == ()


def test_issues_for_mode_selects_by_mode() -> None:
    names = {issue.id for issue in issues_for_mode("spb_s")}
    assert names == {
        "no_chemical_potential",
        "interpolation_extrapolates",
    }


@pytest.mark.parametrize("name", [*SPB, *DPB])
def test_repaired_modes_are_enabled(name: str) -> None:
    assert not fit_mode(name).disabled


@pytest.mark.parametrize("kind", ["measured", "chemical_potential", "thermal_conductivity", None])
def test_repaired_hall_flags_are_removed_from_every_result(kind: Any) -> None:
    assert not {"spb_hall_mode_disabled", "spb_hall_uses_fermi_energy"} & set(
        ids("spb_s_rho_rh", "acPh", kind)
    )


def test_a_flag_for_one_scattering_type_stays_there() -> None:
    assert "hall_dis_no_reference" in ids("dpb_s_rho_rh", "dis")
    assert "hall_dis_no_reference" not in ids("dpb_s_rho_rh", "acPh")
    assert "acphdis_curve_scale" not in ids("dpb_s_rho", "acPh", "thermal_conductivity")
    assert "acphdis_curve_scale" not in ids("dpb_s_rho", "ionized", "seebeck_by_band")


@pytest.mark.parametrize("ratio", [0.5, 2.0, 3.0])
@pytest.mark.parametrize(
    "kind",
    [None, "measured", "seebeck_by_band", "chemical_potential", "carrier_concentration_by_band"],
)
def test_dpb_s_has_no_degeneracy_flag_at_any_ratio(ratio: float, kind: CurveKind | None) -> None:
    # P6 fits and draws DPB S with the same R/N, so no flag on N2/N1 applies to it any more.
    assert not {issue for issue in ids("dpb_s", None, kind, ratio=ratio) if "degeneracy" in issue}


@pytest.mark.parametrize(
    ("condition_kwargs", "mode", "scattering", "kind", "issue", "active"),
    [
        ({"ratio": 2.0}, "dpb_s_rho", "acPh", None, "dpb_loop_degeneracy", True),
        ({"ratio": 2.0}, "dpb_s_rho", "acPh", "measured", "dpb_loop_degeneracy", False),
        ({"parameters": {"m_eff": 1.0}}, "dpb_s", None, None, "collapsed_m_eff", False),
        (
            {"parameters": {"m_eff": COLLAPSED_M_EFF / 2}},
            "dpb_s_rho",
            "acPh",
            None,
            "collapsed_m_eff",
            True,
        ),
        (
            {"parameters": {"m_eff": -COLLAPSED_M_EFF / 2}},
            "dpb_s_rho",
            "acPh",
            "measured",
            "collapsed_m_eff",
            True,
        ),
        (
            {"parameters": {"band_mass": 1.0, "fermi_energy": 100.0}},
            "spb_s",
            None,
            None,
            "no_chemical_potential",
            False,
        ),
        (
            {"parameters": {"band_mass": -1.0, "fermi_energy": -100.0}},
            "spb_s",
            None,
            "measured",
            "no_chemical_potential",
            False,
        ),
        (
            {"parameters": {"band_mass": 1.0, "fermi_energy": -100.0}},
            "spb_s",
            None,
            "measured",
            "no_chemical_potential",
            True,
        ),
        (
            {"parameters": {"band_mass": -1.0, "fermi_energy": 100.0}},
            "spb_s",
            None,
            None,
            "no_chemical_potential",
            True,
        ),
        (
            {"parameters": {"band_mass": 1.0, "fermi_energy": 0.0}},
            "spb_s",
            None,
            None,
            "no_chemical_potential",
            True,
        ),
        ({"extrapolated": False}, "spb_s", None, None, "interpolation_extrapolates", False),
        ({"extrapolated": True}, "spb_s", None, None, "interpolation_extrapolates", True),
        ({"extrapolated": True}, "dpb_s", None, "measured", "interpolation_extrapolates", True),
    ],
)
def test_conditions_are_checked(
    condition_kwargs: dict[str, Any],
    mode: str,
    scattering: str | None,
    kind: Any,
    issue: str,
    active: bool,
) -> None:
    assert (issue in ids(mode, scattering, kind, **condition_kwargs)) is active


def synthetic(fit_mode_id: str) -> dict[Any, Measurement]:
    temperature_k = np.linspace(100.0, 800.0, 12)
    values = {"seebeck": 1e-4, "resistivity": 1e-5, "hall": 1e-7}
    return {
        quantity: Measurement(temperature_k, values[quantity] * temperature_k / 100.0)
        for quantity in fit_mode(fit_mode_id).quantities
    }


def curve_ids(fit_mode_id: str, scattering: str | None = None, **kw: Any) -> set[str]:
    model = registry.get(fit_mode_id.partition("_")[0])
    values = default_start(fit_mode(fit_mode_id)) | kw.pop("values", {})
    request = CurveRequest(fit_mode_id, values, 100, 300, 3, scattering, **kw)
    return set(model.calculate(request).known_issues)


@pytest.mark.filterwarnings("ignore")
def test_curves_carry_their_issues_through_the_model() -> None:
    assert curve_ids("dpb_s") == set()
    assert curve_ids("dpb_s", band_2_degeneracy=2.0) == set()
    assert curve_ids("dpb_s", values={"m_eff": -1.0, "band_gap": -200.0}) == set()
    assert curve_ids("dpb_s_rho", "ionized", kind="thermal_conductivity") == set()
    assert curve_ids("dpb_s_rho", "acPh", kind="thermal_conductivity") == set()
    assert curve_ids("dpb_s_rho_rh", "acPh") == set()
    assert curve_ids("spb_s", extrapolated=True) == {"interpolation_extrapolates"}
    # A degeneracy means nothing in SPB, so it is neither read nor checked.
    assert curve_ids("spb_s", band_2_degeneracy=0.0) == set()


class FixedFit:
    """Stands in for the core, returning the given values."""

    def __init__(self, returned: list[float]) -> None:
        self.returned = returned

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: self.returned


def fit_ids(
    monkeypatch: pytest.MonkeyPatch, fit_mode_id: str, returned: list[float], **kw: Any
) -> set[str]:
    from seeband_core import band_models

    monkeypatch.setattr(band_models, "_CORE", FixedFit(returned))
    model = registry.get(fit_mode_id.partition("_")[0])
    values = default_start(fit_mode(fit_mode_id)) | kw.pop("values", {})
    request = FitRequest(
        fit_mode_id, synthetic(fit_mode_id), values, **kw, algorithm="legacy-sequential-v1"
    )
    return set(model.fit(request).known_issues)


def test_a_fit_reads_conditions_from_its_result_not_its_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    negative = fit_ids(monkeypatch, "dpb_s", [-1.0, 500.0, 500.0], values={"m_eff": 1.0})
    assert negative == set()
    positive = fit_ids(monkeypatch, "dpb_s", [1.0, 500.0, 500.0], values={"m_eff": -1.0})
    assert positive == set()
    collapsed = fit_ids(monkeypatch, "dpb_s", [1e-7, 500.0, 500.0])
    assert collapsed == {"collapsed_m_eff"}
    outside = fit_ids(monkeypatch, "spb_s", [-100.0], values={"band_mass": 1.0})
    assert outside == {"no_chemical_potential"}


def test_a_fit_passes_its_degeneracy_and_scattering_on(monkeypatch: pytest.MonkeyPatch) -> None:
    loop = [1.0, 500.0, 500.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    with_n = fit_ids(monkeypatch, "dpb_s", [1.0, 500.0, 500.0], band_2_degeneracy=2.0)
    assert with_n == set()
    dis = fit_ids(monkeypatch, "dpb_s_rho", loop, scattering="dis")
    assert dis == set()
    acph = fit_ids(monkeypatch, "dpb_s_rho", loop, scattering="acPh", band_2_degeneracy=2.0)
    assert acph == {"dpb_loop_degeneracy"}
    made_up = fit_ids(monkeypatch, "spb_s", [100.0], extrapolated=True)
    assert made_up == {"interpolation_extrapolates"}


def test_a_failed_fit_lists_only_a_disabled_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from seeband_core import band_models

    class Failing:
        def __getattr__(self, name: str) -> Any:
            def fail(*args: Any, **kwargs: Any) -> Any:
                raise ValueError("Residuals are not finite")

            return fail

    monkeypatch.setattr(band_models, "_CORE", Failing())
    dpb = registry.get("dpb").fit(
        FitRequest(
            "dpb_s_rho",
            synthetic("dpb_s_rho"),
            default_start(fit_mode("dpb_s_rho")),
            scattering="acPh",
            algorithm="legacy-sequential-v1",
        )
    )
    assert (dpb.status, dpb.known_issues) == ("failed", ())
    spb = registry.get("spb").fit(
        FitRequest(
            "spb_s_rho_rh",
            synthetic("spb_s_rho_rh"),
            default_start(fit_mode("spb_s_rho_rh")),
            scattering="acPh",
            algorithm="legacy-sequential-v1",
        )
    )
    assert (spb.status, spb.known_issues) == ("failed", ())


def curves(mode: str, scattering: str, kind: CurveKind, values: dict[str, float]) -> Any:
    model = registry.get(mode.partition("_")[0])
    return model.calculate(CurveRequest(mode, values, 100, 800, 8, scattering, kind)).curves


@pytest.mark.filterwarnings("ignore")
class TestTheErrorsAreStillThere:
    """Each of these fails once its error is fixed, and that is the prompt to remove its flag."""

    def test_ionized_conductivity_is_the_inverse_of_resistivity(self) -> None:
        for mode in ("spb_s_rho", "dpb_s_rho"):
            values = default_start(fit_mode(mode))
            rho = curves(mode, "ionized", "measured", values)["resistivity_ohm_m"]
            sigma = curves(mode, "ionized", "electrical_conductivity", values)[
                "electrical_conductivity_s_per_m"
            ]
            assert np.allclose(sigma * rho, 1.0)
            rho = curves(mode, "acPh", "measured", values)["resistivity_ohm_m"]
            sigma = curves(mode, "acPh", "electrical_conductivity", values)[
                "electrical_conductivity_s_per_m"
            ]
            assert np.allclose(sigma * rho, 1.0)
