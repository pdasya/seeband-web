import ast
import tomllib
from pathlib import Path

import seeband_core


def test_core_version_is_the_package_version_source() -> None:
    package_root = Path(__file__).parents[1]
    config = tomllib.loads((package_root / "pyproject.toml").read_text())

    assert getattr(seeband_core, "__version__", None) == "0.1.1"
    assert "version" not in config["project"]
    assert "version" in config["project"]["dynamic"]
    version_path = config["tool"]["hatch"]["version"]["path"]
    assert version_path == "src/seeband_core/__init__.py"
    source = ast.parse((package_root / version_path).read_text())
    versions = [
        ast.literal_eval(node.value)
        for node in source.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
    ]
    assert versions == [seeband_core.__version__]
