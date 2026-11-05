import importlib.util
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI

SUPPORT_DIR = Path(__file__).parent / "support"


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
