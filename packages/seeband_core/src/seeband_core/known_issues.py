"""Known errors of the ported calculations, which stay until the Physics fixes stage.

Users must see these, not receive doubtful numbers as if they were sound. To remove a flag once its
error is fixed, delete its entry here. Text a user sees comes from `message_key`, through i18n.
"""

from collections.abc import Mapping

from seeband_core.model_interface import CurveKind, FitMode, KnownIssue

_ALL_CONDUCTIVITY: tuple[CurveKind, ...] = (
    "electrical_conductivity",
    "electrical_conductivity_by_band",
    "thermal_conductivity",
)
DPB_ITERATIVE = ("dpb_s_rho", "dpb_s_rho_rh")
ALL_MODES = ("spb_s", "spb_s_rho", "spb_s_rho_rh", "dpb_s", "dpb_s_rho", "dpb_s_rho_rh")

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
        affects_fit=True,
        explanation="SPB R_H uses the Fermi energy at 0 K instead of the chemical potential",
    ),
    KnownIssue(
        id="dpb_hall_prefactor",
        severity="unreliable",
        fixed_by="#81",
        fit_modes=("dpb_s_rho_rh",),
        curve_kinds=("measured", "carrier_concentration_by_band"),
        affects_fit=True,
        explanation="DPB R_H is half of what it should be, so m1 and n from it are too low",
    ),
    KnownIssue(
        id="acphdis_conductivity_scale",
        severity="unreliable",
        fixed_by="#82",
        fit_modes=("spb_s_rho", "spb_s_rho_rh", "dpb_s_rho", "dpb_s_rho_rh"),
        scattering=("acPhDis",),
        curve_kinds=_ALL_CONDUCTIVITY,
        explanation="With acPhDis, sigma and kappa use another scale from rho, so sigma * rho != 1",
    ),
    KnownIssue(
        id="acphdis_band_weight",
        severity="unreliable",
        fixed_by="#102",
        fit_modes=DPB_ITERATIVE,
        scattering=("acPhDis",),
        curve_kinds=("measured", "seebeck"),
        affects_fit=True,
        explanation="With acPhDis, the band weight of the last temperature applies to all of S",
    ),
    KnownIssue(
        id="acphdis_early_stop",
        severity="caution",
        fixed_by="#84",
        fit_modes=DPB_ITERATIVE,
        scattering=("acPhDis",),
        affects_fit=True,
        explanation="With acPhDis, the fit can stop when only C and D have settled (D18)",
    ),
    KnownIssue(
        id="dpb_s_degeneracy",
        severity="unreliable",
        fixed_by="#85",
        fit_modes=("dpb_s",),
        curve_kinds=("measured",),
        affects_fit=True,
        condition="degeneracy_not_one",
        explanation="With N2/N1 other than 1, a fitted m_eff does not match its curve (D12)",
    ),
    KnownIssue(
        id="negative_m_eff_weight",
        severity="caution",
        fixed_by="#104",
        fit_modes=("dpb_s", "dpb_s_rho", "dpb_s_rho_rh"),
        curve_kinds=(
            "measured",
            "seebeck",
            "seebeck_by_band",
            *_ALL_CONDUCTIVITY,
        ),
        affects_fit=True,
        condition="negative_m_eff",
        explanation="With m_eff below 0, band 2 gets a negative weight, for a physicist to check",
    ),
    KnownIssue(
        id="hall_dis_web_bounds",
        severity="caution",
        fixed_by="#71",
        fit_modes=("dpb_s_rho_rh",),
        scattering=("dis",),
        affects_fit=True,
        explanation="This fit fails on the desktop (D1). It runs here with other bounds of G, so "
        "there is no desktop result to compare with.",
    ),
    KnownIssue(
        id="interpolation_extrapolates",
        severity="unreliable",
        fixed_by="#86",
        fit_modes=ALL_MODES,
        condition="interpolation_extrapolated",
        explanation="Interpolation made up points beyond the data, and they enter the fit",
    ),
)


def issues_for_mode(fit_mode_id: str) -> tuple[KnownIssue, ...]:
    return tuple(issue for issue in KNOWN_ISSUES if fit_mode_id in issue.fit_modes)


def active_issue_ids(
    fit_mode: FitMode,
    scattering: str | None,
    parameters: Mapping[str, float],
    degeneracy_ratio: float,
    kind: CurveKind | None = None,
    extrapolated: bool = False,
) -> tuple[str, ...]:
    """Return the issues that apply to one result: a fit, or with `kind`, one kind of curve."""
    active = []
    for issue in fit_mode.known_issues:
        if issue.scattering and scattering not in issue.scattering:
            continue
        if issue.condition == "interpolation_extrapolated":
            # This depends on the data a result used, whatever kind of result it is.
            applies = extrapolated
        else:
            applies = kind in issue.curve_kinds if kind is not None else issue.affects_fit
        if issue.condition == "degeneracy_not_one" and degeneracy_ratio == 1:
            applies = False
        if issue.condition == "negative_m_eff" and parameters.get("m_eff", 1.0) >= 0:
            applies = False
        if applies:
            active.append(issue.id)
    return tuple(active)
