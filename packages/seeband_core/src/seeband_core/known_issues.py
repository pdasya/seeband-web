"""Known errors of the ported calculations, which stay until the Physics fixes stage.

Users must see these, not receive doubtful numbers as if they were sound. To remove a flag once its
error is fixed, delete its entry here, with its row in docs/known-issues.md and its i18n text. Text
a user sees comes from `message_key`, through i18n.
"""

from collections.abc import Mapping

from seeband_core.model_interface import CurveKind, FitMode, KnownIssue

_DPB_FIT_CURVES: tuple[CurveKind, ...] = (
    "measured",
    "seebeck",
    "seebeck_by_band",
    "electrical_conductivity",
    "electrical_conductivity_by_band",
    "thermal_conductivity",
)
_ALL_CURVES: tuple[CurveKind, ...] = (
    *_DPB_FIT_CURVES,
    "chemical_potential",
    "carrier_concentration_by_band",
)
_SPB_MODES = ("spb_s", "spb_s_rho", "spb_s_rho_rh")
_DPB_MODES = ("dpb_s", "dpb_s_rho", "dpb_s_rho_rh")
_DPB_LOOP = ("dpb_s_rho", "dpb_s_rho_rh")
# Below this, the second band has no weight left in a fit (D19).
COLLAPSED_M_EFF = 1e-5

KNOWN_ISSUES: tuple[KnownIssue, ...] = (
    KnownIssue(
        id="spb_hall_mode_disabled",
        severity="disabled",
        fixed_by="#83",
        fit_modes=("spb_s_rho_rh",),
        affects_fit=True,
        explanation="This fit fails on the desktop, and its mass and scales are wrong (D2, D3, D6)",
    ),
    KnownIssue(
        id="spb_hall_uses_fermi_energy",
        severity="unreliable",
        fixed_by="#103",
        fit_modes=("spb_s_rho_rh",),
        curve_kinds=("measured",),
        columns=("hall_m3_per_c",),
        affects_fit=True,
        explanation="SPB R_H uses the Fermi energy at 0 K instead of the chemical potential",
    ),
    KnownIssue(
        id="acphdis_curve_scale",
        severity="unreliable",
        fixed_by="#82",
        fit_modes=("spb_s_rho", "spb_s_rho_rh", "dpb_s_rho", "dpb_s_rho_rh"),
        scattering=("acPhDis",),
        curve_kinds=(
            "seebeck_by_band",
            "electrical_conductivity",
            "electrical_conductivity_by_band",
            "thermal_conductivity",
        ),
        explanation="With acPhDis, these curves use another scale of C and D from rho and S, so "
        "sigma * rho != 1 and band contributions do not sum to S",
    ),
    KnownIssue(
        id="acphdis_band_weight",
        severity="unreliable",
        fixed_by="#102",
        fit_modes=_DPB_LOOP,
        scattering=("acPhDis",),
        curve_kinds=("measured", "seebeck"),
        columns=("seebeck_v_per_k",),
        affects_fit=True,
        explanation="With acPhDis, the band weight of the last temperature applies to all of S",
    ),
    KnownIssue(
        id="acphdis_early_stop",
        severity="unreliable",
        fixed_by="#84",
        fit_modes=_DPB_LOOP,
        scattering=("acPhDis",),
        affects_fit=True,
        explanation="With acPhDis, the fit stops when C and D alone settle, as every recorded fit "
        "on the 3 examples did (D18)",
    ),
    KnownIssue(
        id="dpb_s_degeneracy",
        severity="unreliable",
        fixed_by="#85",
        fit_modes=("dpb_s",),
        curve_kinds=(
            "measured",
            "seebeck_by_band",
            "chemical_potential",
            "carrier_concentration_by_band",
        ),
        affects_fit=True,
        condition="degeneracy_not_one",
        explanation="With N2/N1 other than 1, a fitted m_eff does not match its curves (D12)",
    ),
    KnownIssue(
        id="dpb_loop_degeneracy",
        severity="caution",
        fixed_by="#85",
        fit_modes=_DPB_LOOP,
        affects_fit=True,
        condition="degeneracy_not_one",
        explanation="With N2/N1 other than 1, the fit returns m_eff times N, which can leave its "
        "bounds (D12)",
    ),
    KnownIssue(
        id="negative_m_eff_weight",
        severity="caution",
        fixed_by="#104",
        fit_modes=_DPB_MODES,
        curve_kinds=_DPB_FIT_CURVES,
        affects_fit=True,
        condition="negative_m_eff",
        explanation="With m_eff below 0, band 2 gets a negative weight, for a physicist to check",
    ),
    KnownIssue(
        id="collapsed_m_eff",
        severity="unreliable",
        fixed_by="#107",
        fit_modes=_DPB_MODES,
        curve_kinds=_ALL_CURVES,
        affects_fit=True,
        condition="collapsed_m_eff",
        explanation="m_eff near 0 removes the weight of the other band, so the data do not settle "
        "the fit, and it differs between machines (D19)",
    ),
    KnownIssue(
        id="no_chemical_potential",
        severity="unreliable",
        fixed_by="#106",
        fit_modes=_SPB_MODES,
        curve_kinds=(
            "measured",
            "chemical_potential",
            "electrical_conductivity",
            "thermal_conductivity",
        ),
        affects_fit=True,
        condition="fermi_energy_outside_band",
        explanation="With the Fermi energy outside the band, there are no carriers, and the solved "
        "chemical potential and curves mean nothing",
    ),
    KnownIssue(
        id="hall_dis_no_reference",
        severity="caution",
        fixed_by="#71",
        fit_modes=("dpb_s_rho_rh",),
        scattering=("dis",),
        affects_fit=True,
        explanation="This fit fails on the desktop (D1). It runs here with other bounds of G, so "
        "there is no desktop result to compare with",
    ),
    KnownIssue(
        id="band_diagram_formula",
        severity="caution",
        fixed_by="#108",
        fit_modes=(*_SPB_MODES, *_DPB_MODES),
        affects_band_diagram=True,
        explanation="The sketch of E(k) follows no E = hbar^2 k^2 / 2m in any stated units. It "
        "enters no fit or curve, so no result lists this, only the diagram itself",
    ),
    KnownIssue(
        id="interpolation_extrapolates",
        severity="unreliable",
        fixed_by="#86",
        fit_modes=(*_SPB_MODES, *_DPB_MODES),
        condition="interpolation_extrapolated",
        explanation="Interpolation made up points beyond the data, and they enter the fit",
    ),
)


def issues_for_mode(fit_mode_id: str) -> tuple[KnownIssue, ...]:
    return tuple(issue for issue in KNOWN_ISSUES if fit_mode_id in issue.fit_modes)


def _condition_holds(
    issue: KnownIssue,
    parameters: Mapping[str, float],
    degeneracy_ratio: float,
    extrapolated: bool,
) -> bool:
    if issue.condition == "degeneracy_not_one":
        return degeneracy_ratio != 1
    if issue.condition == "negative_m_eff":
        return parameters.get("m_eff", 1.0) < 0
    if issue.condition == "collapsed_m_eff":
        return abs(parameters.get("m_eff", 1.0)) < COLLAPSED_M_EFF
    if issue.condition == "fermi_energy_outside_band":
        return parameters.get("band_mass", 1.0) * parameters.get("fermi_energy", 1.0) <= 0
    if issue.condition == "interpolation_extrapolated":
        return extrapolated
    return True


def active_issue_ids(
    fit_mode: FitMode,
    scattering: str | None,
    parameters: Mapping[str, float],
    degeneracy_ratio: float,
    kind: CurveKind | None = None,
    extrapolated: bool = False,
) -> tuple[str, ...]:
    """Return the issues that apply to one result: a fit, or with `kind`, one kind of curve.

    A disabled mode shows on every result. An issue with data as its cause shows on any result.
    """
    active = []
    for issue in fit_mode.known_issues:
        if issue.scattering and scattering not in issue.scattering:
            continue
        if issue.severity == "disabled" or issue.condition == "interpolation_extrapolated":
            in_scope = True
        else:
            in_scope = kind in issue.curve_kinds if kind is not None else issue.affects_fit
        if in_scope and _condition_holds(issue, parameters, degeneracy_ratio, extrapolated):
            active.append(issue.id)
    return tuple(active)


def band_diagram_issue_ids(fit_mode: FitMode) -> tuple[str, ...]:
    """Return what the sketch of E(k) carries, which no fit or curve does."""
    return tuple(issue.id for issue in fit_mode.known_issues if issue.affects_band_diagram)


def disabled_issue_ids(fit_mode: FitMode) -> tuple[str, ...]:
    """Return what a failed fit still reports: nothing about its numbers, only the mode's state."""
    return tuple(issue.id for issue in fit_mode.known_issues if issue.severity == "disabled")
