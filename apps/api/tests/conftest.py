import importlib.util
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI

SUPPORT_DIR = Path(__file__).parent / "support"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keeps a developer's own settings out of the tests."""
    for name in os.environ:
        if name.startswith("SEEBAND_API_"):
            monkeypatch.delenv(name)


@pytest.fixture
def leaky_app_factory() -> Callable[[], FastAPI]:
    spec = importlib.util.spec_from_file_location("leaky_app", SUPPORT_DIR / "leaky_app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    create_app: Callable[[], FastAPI] = module.create_app
    return create_app


@pytest.fixture
def support_dir() -> Path:
    return SUPPORT_DIR
