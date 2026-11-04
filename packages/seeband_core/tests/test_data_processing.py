import numpy as np
import pytest
from seeband_core import data_processing


def test_validate_data_keeps_valid_lines_and_leaves_its_input_unchanged() -> None:
    lines = ["T S\n", "300 1.5\n", "not a number\n", "400,2e-6\n"]
    before = list(lines)
    assert data_processing.validate_data(lines) == ["300 1.5\n", "400,2e-6\n"]
    assert lines == before


def test_validate_data_rejects_input_with_no_valid_line() -> None:
    with pytest.raises(Exception, match="no valid entry"):
        data_processing.validate_data(["T S\n"])


@pytest.mark.parametrize("line", ["300 1.5\n", "300\t1.5\n", "300,1.5\n"])
def test_format_data_splits_on_each_separator(line: str) -> None:
    assert np.array_equal(data_processing.format_data([line]), [[300.0, 1.5]])


def test_fit_data_logs_a_failure_and_returns_none(caplog: pytest.LogCaptureFixture) -> None:
    assert data_processing.fit_data(np.array([1.0, 2.0])) is None
    assert "fit_data" in caplog.text
