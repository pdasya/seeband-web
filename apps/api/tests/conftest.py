import importlib.util
import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI

SUPPORT_DIR = Path(__file__).parent / "support"
# Spawned workers inherit this path, so they can import test functions from there.
sys.path.insert(0, str(SUPPORT_DIR))


# Keeps a developer's own settings out of the tests, including fixtures shared across a module.
for _name in list(os.environ):
    if _name.startswith("SEEBAND_API_"):
        del os.environ[_name]
# Tests send requests far faster than a person, including through servers they start. Those that
# check the rate limits set their own.
for _name in ("CALC", "PARSE", "GUESS", "FIT"):
    os.environ[f"SEEBAND_API_{_name}_PER_MINUTE"] = "1000000"


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
