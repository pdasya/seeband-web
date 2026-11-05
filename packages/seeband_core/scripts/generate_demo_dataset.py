"""Write the synthetic demo dataset into the source tree. See docs/demo-dataset.md."""

import json
from pathlib import Path

from seeband_core.demo_dataset import generate_demo_dataset

TARGET = Path(__file__).parents[1] / "src" / "seeband_core" / "data" / "demo_dataset.json"


def main() -> None:
    TARGET.write_text(json.dumps(generate_demo_dataset(), indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
