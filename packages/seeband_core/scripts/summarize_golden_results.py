"""Write docs/golden-results-summary.md from the golden results and the desktop mode table."""

import json
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).parents[1]
GOLDEN = PACKAGE / "tests" / "fixtures" / "golden"
TABLE = PACKAGE / "src" / "seeband_core" / "data" / "desktop_modes.json"
OUTPUT = PACKAGE / "docs" / "golden-results-summary.md"
EXAMPLES = ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]
# Parameters in the order a fit returns them, from fit_module.py.
RESULT_ORDER = {
    "spb_s": ["fermi_energy"],
    "spb_s_rho": ["fermi_energy", "A", "C", "F"],
    "dpb_s": ["m_eff", "band_gap", "fermi_energy"],
    "dpb_s_rho": ["m_eff", "band_gap", "fermi_energy", "A", "B", "C", "D", "F", "G"],
    "dpb_s_rho_rh": ["m_eff", "band_gap", "fermi_energy", "A", "B", "C", "D", "F", "G", "m1"],
}
# Positions of the start values and bounds in each fit call, from seeband.py.
SEE_ARGS = {
    "spb_s": (3, 4),
    "spb_s_rho": (5, 6),
    "dpb_s": (2, 3),
    "dpb_s_rho": (4, 5),
    "dpb_s_rho_rh": (6, 7),
}
RES_ARGS = {"spb_s_rho": (7, 8), "dpb_s_rho": (6, 7), "dpb_s_rho_rh": (8, 9)}
HALL_ARGS = {"dpb_s_rho_rh": (10, 11)}
WARNING_WORDS = {
    "not making good progress": "slow `fsolve`",
    "maxfev": "`fsolve` call limit",
    "divide by zero": "division by zero",
    "overflow": "overflow",
}
BOUND_TOLERANCE = 1e-6
UNMOVED_TOLERANCE = 1e-9


def start_and_bounds(mode: str, args: list[Any]) -> dict[str, tuple[float, float, float]]:
    """Return each parameter's start value and bounds as the fit call received them."""
    names = iter(RESULT_ORDER[mode])
    found = {}
    for positions in (SEE_ARGS, RES_ARGS):
        if mode in positions:
            start, limits = positions[mode]
            for index, value in enumerate(args[start]):
                found[next(names)] = (value, args[limits][0][index], args[limits][1][index])
    if mode in HALL_ARGS:
        start, limits = HALL_ARGS[mode]
        found[next(names)] = (args[start], limits_of(args[limits])[0], limits_of(args[limits])[1])
    return found


def limits_of(limits: list[list[float]]) -> tuple[float, float]:
    return limits[0][0], limits[1][0]


def near(value: float, target: float, tolerance: float) -> bool:
    return abs(value - target) <= tolerance * max(1.0, abs(target))


def fitted_names(mode: dict[str, Any], scattering: str | None) -> set[str]:
    return {
        parameter["name"]
        for parameter in mode["parameters"]
        if parameter["role"] == "fitted"
        and (scattering is None or scattering in parameter["scattering"])
    }


def findings(
    mode: dict[str, Any], scattering: str | None, call: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """Return fitted parameters that stopped at a bound, and those that did not move."""
    received = start_and_bounds(mode["id"], call["args"])
    fitted = fitted_names(mode, scattering)
    at_bound, unmoved = [], []
    for name, value in zip(RESULT_ORDER[mode["id"]], call["result"], strict=False):
        if name not in fitted:
            continue
        start, lower, upper = received[name]
        # Scattering parameters at 300 K are multiplied inside the fit, not in these bounds.
        if near(value, lower, BOUND_TOLERANCE) or near(value, upper, BOUND_TOLERANCE):
            at_bound.append(f"`{name}` = {value:.4g}")
        elif abs(value - start) <= UNMOVED_TOLERANCE * max(1.0, abs(start)):
            unmoved.append(f"`{name}`")
    return at_bound, unmoved


def warning_words(warnings: list[str]) -> str:
    words = [word for key, word in WARNING_WORDS.items() if any(key in text for text in warnings)]
    return ", ".join(words) or "none"


def render(golden: dict[str, dict[str, Any]], table: dict[str, Any]) -> str:
    modes = {mode["id"]: mode for mode in table["modes"]}
    rows, ran, doubtful = [], 0, 0
    for name in EXAMPLES:
        for run in golden[name]["runs"]:
            mode = modes[run["mode"]]
            at_bound: list[str] = []
            unmoved: list[str] = []
            if run["status"] == "ok":
                ran += 1
                at_bound, unmoved = findings(mode, run["scattering"], run["calls"][0])
                doubtful += bool(at_bound or unmoved)
            rows.append(
                f"| {name[:2]} | {mode['model']} {mode['fit_mode']} | {run['scattering'] or ''} "
                f"| {run['status']} | {run['iterations'] or ''} | {run['stop_path'] or ''} "
                f"| {', '.join(at_bound)} | {', '.join(unmoved)} "
                f"| {warning_words(run['warnings'])} |"
            )
    extra = []
    for name in EXAMPLES:
        run = golden[name]["d1_with_g_minimum_1"]
        at_bound, unmoved = findings(modes["dpb_s_rho_rh"], "dis", run["calls"][0])
        extra.append(
            f"| {name[:2]} | {run['status']} | {', '.join(at_bound)} | {', '.join(unmoved)} "
            f"| {warning_words(run['warnings'])} |"
        )
    header = [
        "# Golden results summary",
        "",
        "Generated by `scripts/summarize_golden_results.py` from the golden results. Do not edit.",
        "",
        f"In {doubtful} of {ran} successful runs, a fitted parameter stops at a bound or does not "
        "move from its start value. Parameters that a scattering type does not fit are left out.",
        "",
        "| Ex. | Mode | Scattering | Status | Iterations | Stop path | At a bound | Did not move "
        "| Warnings |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    d1 = [
        "",
        "## DPB S+rho+R_H with dis, G slider minimum 1",
        "",
        "G bounds here are 1 to 200, so this is not a reference for the web bounds of 0.5 to 2.",
        "",
        "| Ex. | Status | At a bound | Did not move | Warnings |",
        "| --- | --- | --- | --- | --- |",
    ]
    return "\n".join(header + rows + d1 + extra) + "\n"


def load() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    golden = {
        name: json.loads((GOLDEN / f"{name}.json").read_text(encoding="utf-8")) for name in EXAMPLES
    }
    return golden, json.loads(TABLE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    OUTPUT.write_text(render(*load()), encoding="utf-8")
