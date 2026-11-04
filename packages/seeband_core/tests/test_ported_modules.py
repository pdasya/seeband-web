import hashlib
import json
import os
import subprocess
import sys
from importlib import resources
from pathlib import Path

import pytest

IMPORT_AND_USE = """
from seeband_core import data_processing, fit_module, math_module
assert math_module.fermi1_10.shape == (30000, 2)
assert math_module.fermi1_10[0, 0] == -10.0
assert math_module.fermi1_10[-1, 0] == 19.999
assert fit_module.PB_fit() is not None
assert callable(data_processing.get_data)
"""
GOLDEN = Path(__file__).parent / "fixtures" / "golden" / "01_Fe2VAl09Si01.json"
TABLE_SHA256 = "f22e78451a38c57ae00715a0e68631e5dc434b7a3c97f1a45b4d26e0a2ffdd43"


def package_file(*parts: str) -> bytes:
    path = resources.files("seeband_core").joinpath(*parts)
    return path.read_bytes()


def test_modules_import_from_any_working_directory(tmp_path: Path) -> None:
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_AND_USE],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_fermi_table_is_unchanged() -> None:
    content = package_file("data", "fermi_int_-10_20.txt")
    assert hashlib.sha256(content).hexdigest() == TABLE_SHA256


def test_ported_calculation_matches_a_recorded_curve() -> None:
    from seeband_core import fit_module

    document = json.loads(GOLDEN.read_text(encoding="utf-8"))
    run = next(run for run in document["runs"] if run["mode"] == "dpb_s")
    call = run["manual_curve_calls"][0]
    assert call["function"] == "dpb_see_calc"
    temperature, seebeck = fit_module.PB_fit().dpb_see_calc(*call["args"])
    assert list(temperature) == pytest.approx(call["result"][0])
    assert list(seebeck) == pytest.approx(call["result"][1], rel=1e-5)
