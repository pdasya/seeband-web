# seeband_core

The new [single Kane band model](docs/kane-model.md), registered as `skb`, jointly
fits S(T), rho(T) and R_H(T), and provides E(k) and derived temperature curves.
`band_models.SkbModel` uses the same adapter and parameter conventions as SPB/DPB.

Band model calculations and fits, ported from the SeeBand desktop application. It has no dependency on Qt, TensorFlow or FastAPI. `math_module`, `fit_module`, `data_processing` and `neural_nets` come from SeeBand. `neural_nets` runs the desktop nets with numpy from exported weights. They do not print or change their inputs. Their results match the desktop within the tolerances and with the exceptions listed in [golden results](docs/golden-results.md), including the DPB fits on `02_SiP` that cannot match it (D19).

These modules, `neural_nets`, the neural net weights and the Fermi table keep the original SeeBand [license](LICENSE). The rest of the package is under the [project license](LICENSE-seeband-web). Both are MIT.

`band_models` runs SPB and DPB behind the model interface, and `model_catalog` registers them. [Demo dataset](docs/demo-dataset.md) describes the synthetic data for visitors. [Known issues](docs/known-issues.md) lists the errors flagged until the physics fixes. [Interpolation](docs/interpolation.md) gives the semantics of `interpolation`. [Input data](docs/input-data.md) describes what `data_parser` reads. [Adding a model](docs/adding-a-model.md) explains the model interface and registry. [Desktop modes](docs/desktop-modes.md) records what the desktop application passes to its calculations in each mode, including where it is inconsistent. [Neural net references](docs/neural-net-references.md) records the outputs of the desktop neural nets and how to regenerate them. [Golden results](docs/golden-results.md) records what the desktop computes on the examples, captured from its real window. `tests/test_golden_regression.py` compares the ported modules with those results.
