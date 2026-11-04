"""Capture golden results by driving the real SeeBand desktop window without a screen.

Needs a clean SeeBand checkout at the reference commit and an environment with TensorFlow,
PyQt5, pyqtgraph, scipy and mpmath. It is not part of the normal setup. See
docs/golden-results.md for the command and versions.
"""

import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
import platform
import re
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

DESKTOP_COMMIT = "803b0e7a425a0a3f4f59688df77e3ad283ca49a1"
EXAMPLES = ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]
SCATTERING = ["acPh", "dis", "acPhDis"]
# id, thread class, handler that recalculates the curve, window suffix, scattering combo box
MODES = [
    ("spb_s", "FittingThreadSpbSee", "manipulate_value_changed_spb_see", "spb_see", None),
    ("spb_s_rho", "FittingThreadSpbRes", "manipulate_value_changed_spb_res", "spb_res", "spb_res"),
    (
        "spb_s_rho_rh",
        "FittingThreadSpbHall",
        "manipulate_value_changed_spb_hall",
        "spb_hall",
        "spb_hall",
    ),
    ("dpb_s", "FittingThreadDpbSee", "manipulate_value_changed_dpb_see", "dpb_see", None),
    ("dpb_s_rho", "FittingThreadDpbRes", "manipulate_value_changed_dpb_res", "dpb_res", "dpb_res"),
    (
        "dpb_s_rho_rh",
        "FittingThreadDpbHall",
        "manipulate_value_changed_dpb_hall",
        "dpb_hall",
        "dpb_hall",
    ),
]


def plain(value: Any) -> Any:
    """Convert numpy values to JSON types without changing any number."""
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [plain(item) for item in value]
    return value


class RecordingCalculator:
    """Stands in for the desktop's TE object and records every call with its exact arguments."""

    def __init__(self, target: Any) -> None:
        self._target = target
        self.calls: list[dict[str, Any]] = []
        # The loop has two stop checks, and only their argument counts tell them apart.
        self.accuracy_checks: list[tuple[int, bool]] = []
        original = target.is_accuracy_reached

        def watched(threshold: float, *errors: float) -> bool:
            reached = bool(original(threshold, *errors))
            self.accuracy_checks.append((len(errors), reached))
            return reached

        target.is_accuracy_reached = watched

    def __getattr__(self, name: str) -> Any:
        method = getattr(self._target, name)
        if not callable(method):
            return method

        def call(*args: Any, **kwargs: Any) -> Any:
            # Fit functions change the lists they receive, so copy before the call.
            record: dict[str, Any] = {
                "function": name,
                "args": plain(copy.deepcopy(args)),
                "kwargs": plain(copy.deepcopy(kwargs)),
            }
            self.calls.append(record)
            try:
                result = method(*args, **kwargs)
            except Exception as error:
                record["error"] = f"{type(error).__name__}: {error}"
                raise
            record["result"] = plain(result)
            return result

        return call


def run_fit(desktop: Any, window: Any, recorder: RecordingCalculator, thread_name: str) -> Any:
    """Run a fit thread's body synchronously, so the calls and result are captured in order."""
    recorder.calls.clear()
    recorder.accuracy_checks.clear()
    outcome: dict[str, Any] = {}
    thread = getattr(desktop, thread_name)(window)
    thread.updateGUI.connect(lambda *values: outcome.update(emitted=plain(list(values))))
    thread.error_occurred.connect(lambda label: outcome.update(error_signal=label))
    output = io.StringIO()
    with warnings.catch_warnings(record=True) as caught, contextlib.redirect_stdout(output):
        warnings.simplefilter("always")
        thread.run()
    outcome["warnings"] = sorted({str(item.message).strip()[:160] for item in caught})
    errors = [
        line[len("Exception: ") :]
        for line in output.getvalue().splitlines()
        if line.startswith("Exception: ")
    ]
    outcome["printed_error"] = errors[0] if errors else None
    # Only iterative fits print these lines, and only the desktop's own log says why they stopped.
    log = output.getvalue()
    outcome["stopped_by"] = (
        "iteration_limit"
        if "Error! Fitting not possible" in log
        else "accuracy"
        if "Accuracy reached." in log
        else None
    )
    iterations = re.findall(r"It took (\d+) iterations", log)
    outcome["iterations"] = int(iterations[-1]) if iterations else None
    outcome["stop_path"] = stop_path(recorder.accuracy_checks)
    outcome["calls"] = copy.deepcopy(recorder.calls)
    return outcome


def stop_path(checks: list[tuple[int, bool]]) -> str | None:
    """Name the check that ended the loop: fit_module.py:470 and :933, or :474 and :937."""
    for count, reached in reversed(checks):
        if reached:
            return "all_band_and_first_scattering" if count == 5 else "c_and_d_only"
    return None


def summarise(outcome: dict[str, Any]) -> str:
    if "error_signal" not in outcome:
        return "ok"
    failed = [call["function"] for call in outcome["calls"] if "error" in call]
    if failed:
        return "fails_in_" + failed[-1]
    if outcome["calls"]:
        return "fails_after_" + outcome["calls"][-1]["function"]
    return "fails_before_calculation"


def capture_example(
    desktop: Any, application: Any, fit_module: Any, example: str
) -> dict[str, Any]:
    recorder = RecordingCalculator(fit_module.PB_fit())
    desktop.TE = recorder
    window = desktop.MainWindow()

    def load(handler: Any, suffix: str) -> None:
        path = f"data/Examples/{example}_{suffix}.txt"
        desktop.QFileDialog.getOpenFileName = lambda *args, **kwargs: (path, "")
        with contextlib.redirect_stdout(io.StringIO()):
            handler(False)

    load(window.see_databutton_clicked, "see")
    window.model_prediction_thread.wait()
    application.processEvents()
    load(window.res_databutton_clicked, "rho")
    load(window.hall_databutton_clicked, "hall")
    application.processEvents()

    result: dict[str, Any] = {
        "example": example,
        "start_values": {
            suffix: {
                "m_eff": getattr(window, f"mass_slider_{suffix}").value() / 100.0,
                "band_gap_k": getattr(window, f"bandgap_slider_{suffix}").value(),
                "fermi_energy_k": getattr(window, f"fermi_slider_{suffix}").value(),
            }
            for suffix in ("dpb_see", "dpb_res", "dpb_hall")
        },
        "runs": [],
    }
    for mode, thread_name, handler, _suffix, combo in MODES:
        for scattering in SCATTERING if combo else [None]:
            if combo:
                getattr(window, f"scattering_type_{combo}").setCurrentText(scattering)
            recorder.calls.clear()
            with contextlib.redirect_stdout(io.StringIO()):
                getattr(window, handler)()
            manual = copy.deepcopy(recorder.calls)
            outcome = run_fit(desktop, window, recorder, thread_name)
            result["runs"].append(
                {
                    "mode": mode,
                    "scattering": scattering,
                    "status": summarise(outcome),
                    "manual_curve_calls": manual,
                    **outcome,
                }
            )
            sys.stderr.write(f"{example} {mode} {scattering}: {result['runs'][-1]['status']}\n")
            sys.stderr.flush()

    # Whether Advanced options can make DPB S + rho + R_H with dis work, deviation D1.
    window.para_G_slider_dpb_hall.setMinimum(1)
    window.scattering_type_dpb_hall.setCurrentText("dis")
    outcome = run_fit(desktop, window, recorder, "FittingThreadDpbHall")
    result["d1_with_g_minimum_1"] = {"status": summarise(outcome), **outcome}
    window.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desktop", type=Path, required=True, help="SeeBand checkout")
    parser.add_argument("--output", type=Path, required=True, help="Folder for the JSON files")
    parser.add_argument("--examples", nargs="*", default=EXAMPLES, help="Examples to capture")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    desktop_path = args.desktop.resolve()

    sys.dont_write_bytecode = True
    sys.path.insert(0, str(desktop_path))
    os.chdir(desktop_path)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    git = ["git", "-C", str(desktop_path)]
    commit = subprocess.run(
        [*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if commit != DESKTOP_COMMIT:
        raise SystemExit(f"Expected SeeBand commit {DESKTOP_COMMIT}, found {commit}")
    dirty = subprocess.run(
        [*git, "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if dirty:
        raise SystemExit("The SeeBand checkout has local changes")

    import h5py
    import keras
    import mpmath
    import numpy as np
    import PyQt5.QtCore as qt
    import pyqtgraph
    import scipy
    import seeband as desktop
    import tensorflow as tf
    from modules import fit_module
    from PyQt5.QtWidgets import QApplication

    application = QApplication([])
    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "mpmath": mpmath.__version__,
        "tensorflow": tf.__version__,
        "keras": keras.__version__,
        "h5py": h5py.__version__,
        "qt": qt.QT_VERSION_STR,
        "pyqt": qt.PYQT_VERSION_STR,
        "pyqtgraph": pyqtgraph.__version__,
        "qt_platform": os.environ["QT_QPA_PLATFORM"],
    }
    for example in args.examples:
        document = {
            "source": {"repository": "https://github.com/xAngelswordx/SeeBand", "commit": commit},
            "environment": environment,
            "input_files_sha256": {
                suffix: hashlib.sha256(
                    Path(f"data/Examples/{example}_{suffix}.txt").read_bytes()
                ).hexdigest()
                for suffix in ("see", "rho", "hall")
            },
            **capture_example(desktop, application, fit_module, example),
        }
        path = output / f"{example}.json"
        path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
