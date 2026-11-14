# seeband_core

Band model calculations and fits, ported from the SeeBand desktop application. It has no dependency on Qt, TensorFlow or FastAPI. `math_module`, `fit_module`, `data_processing` and `neural_nets` come from SeeBand. `neural_nets` runs the desktop nets with numpy from exported weights. They do not print or change their inputs. Their results match the desktop within the tolerances and with the exceptions listed in [golden results](docs/golden-results.md), including the DPB fits on `02_SiP` that cannot match it (D19).

These modules, `neural_nets`, the neural net weights and the Fermi table keep the original SeeBand [license](LICENSE). The rest of the package is under the [project license](LICENSE-seeband-web). Both are MIT.

`band_models` runs SPB and DPB behind the model interface, and `model_catalog` registers them. [Demo dataset](docs/demo-dataset.md) describes the synthetic data for visitors. [Known issues](docs/known-issues.md) lists the errors flagged until the physics fixes. [Interpolation](docs/interpolation.md) gives the semantics of `interpolation`. [Input data](docs/input-data.md) describes what `data_parser` reads. [Adding a model](docs/adding-a-model.md) explains the model interface and registry. [Desktop modes](docs/desktop-modes.md) records what the desktop application passes to its calculations in each mode, including where it is inconsistent. [Neural net references](docs/neural-net-references.md) records the outputs of the desktop neural nets and how to regenerate them. [Golden results](docs/golden-results.md) records what the desktop computes on the examples, captured from its real window. `tests/test_golden_regression.py` compares the ported modules with those results.

SPB numerical initial estimates and DPB neural guesses are described in [Initial guess](docs/initial-guess.md).

## Calculation versions

`seeband_core.__version__` is the package version source. Core `0.1.0`
identifies the P2–P7 calculation state; the API reports it as `core_version`
on health, curve and fit responses. The API's own `version` remains separate.
Future changes that can alter calculated results need a new core version and
an updated results note; pending fixes must not silently reuse `0.1.0`.

Exports distinguish the core that produced a fit or curve from the server
queried during export. Older results without provenance remain unknown.
Version `0.0.0` was reused during development and cannot identify one numerical
state. A version identifies software behavior, not physical validity or human
physicist confirmation. See [results that changed](../../apps/site/results-changed.md).
