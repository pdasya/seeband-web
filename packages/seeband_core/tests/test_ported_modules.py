import subprocess
import sys
from pathlib import Path

IMPORT_AND_USE = """
from seeband_core import data_processing, fit_module, math_module
assert math_module.fermi1_10.shape[1] == 2
assert len(math_module.fermi1_10) > 0
assert fit_module.PB_fit() is not None
assert data_processing.get_data is not None
"""


def test_modules_import_from_any_working_directory(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_AND_USE],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
