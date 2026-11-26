"""Extended cases are long regressions: skipped by default, run with `-m extended` or by name."""

from pathlib import Path

import pytest


def _named(config: pytest.Config) -> list[str]:
    """Node ids given on the command line, relative to the root like `item.nodeid`."""
    named = []
    for argument in config.args:
        path, separator, rest = argument.partition("::")
        if not separator:
            continue
        try:
            relative = Path(path).resolve().relative_to(config.rootpath).as_posix()
        except ValueError:
            relative = path
        named.append(f"{relative}::{rest}")
    return named


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.option.markexpr:  # -m decides on its own, `-m extended` included
        return
    named = _named(config)
    skip = pytest.mark.skip(reason="extended regression: run with -m extended or name the test")
    for item in items:
        if item.get_closest_marker("extended") is None:
            continue
        if any(item.nodeid == n or item.nodeid.startswith((f"{n}[", f"{n}::")) for n in named):
            continue
        item.add_marker(skip)
