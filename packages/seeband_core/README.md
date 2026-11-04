# seeband_core

Band model calculations and fits, ported from the SeeBand desktop application. It has no dependency on Qt, TensorFlow or FastAPI. `math_module`, `fit_module`, `data_processing` and `neural_nets` come from SeeBand. `neural_nets` runs the desktop nets with numpy from exported weights. They do not print or change their inputs. Their results match the desktop within the tolerances and with the exceptions listed in [golden results](docs/golden-results.md), including the DPB fits on `02_SiP` that cannot match it (D19).

These modules, `neural_nets`, the neural net weights and the Fermi table keep the original SeeBand [license](LICENSE). The rest of the package is under the [project license](LICENSE-seeband-web). Both are MIT.

[Desktop modes](docs/desktop-modes.md) records what the desktop application passes to its calculations in each mode, including where it is inconsistent. [Neural net references](docs/neural-net-references.md) records the outputs of the desktop neural nets and how to regenerate them. [Golden results](docs/golden-results.md) records what the desktop computes on the examples, captured from its real window. `tests/test_golden_regression.py` compares the ported modules with those results.
