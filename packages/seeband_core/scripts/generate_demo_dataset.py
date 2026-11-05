"""Write the synthetic demo dataset. See docs/demo-dataset.md."""

import json
from importlib import resources

from seeband_core.demo_dataset import generate_demo_dataset


def main() -> None:
    path = resources.files("seeband_core") / "data" / "demo_dataset.json"
    with resources.as_file(path) as file:
        file.write_text(json.dumps(generate_demo_dataset(), indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
