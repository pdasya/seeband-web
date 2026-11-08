import math

import pytest
from seeband_core.measured_points import conductivity_points


def test_conductivity_is_one_over_resistivity() -> None:
    assert conductivity_points([1e-5, 2e-5, 0.5]) == pytest.approx([1e5, 5e4, 2.0])


def test_a_resistivity_with_no_conductivity_gives_no_point() -> None:
    assert conductivity_points([0.0, -1e-5, math.inf, math.nan, 1e-5]) == [
        None,
        None,
        None,
        None,
        pytest.approx(1e5),
    ]


def test_the_measured_values_stay_as_they_were() -> None:
    values = [1e-5, 2e-5]
    conductivity_points(values)
    assert values == [1e-5, 2e-5]


def test_no_resistivity_gives_no_points() -> None:
    assert conductivity_points([]) == []
