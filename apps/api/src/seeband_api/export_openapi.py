"""Writes the OpenAPI contract: `python -m seeband_api.export_openapi <file>`."""

import argparse
import json
from pathlib import Path

from seeband_api.main import create_app


def render_openapi() -> str:
    return json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    arguments.output.write_text(render_openapi(), encoding="utf-8")


if __name__ == "__main__":
    main()
