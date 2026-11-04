# seeband_core

Band model calculations and fits, ported from the SeeBand desktop application. It has no dependency on Qt, TensorFlow or FastAPI. `math_module`, `fit_module` and `data_processing` are copied unchanged from SeeBand, apart from imports and how the Fermi table loads. Until C6 cleans them up, they still mutate their inputs and call `print`, and they are excluded from ruff and mypy. `test_ported_modules.py` pins them so that they stay unchanged until then.

These modules and the Fermi table keep the original SeeBand [license](LICENSE). The rest of the package is under the [project license](LICENSE-seeband-web). Both are MIT.

[Desktop modes](docs/desktop-modes.md) records what the desktop application passes to its calculations in each mode, including where it is inconsistent. [Neural net references](docs/neural-net-references.md) records the outputs of the desktop neural nets and how to regenerate them. [Golden results](docs/golden-results.md) records what the desktop computes on the examples, captured from its real window.
