# Neural net references

[`neural_net_references.json`](../tests/fixtures/neural_net_references.json) records the outputs of the SeeBand desktop neural nets, at commit `803b0e7`. The numpy port compares against it, and golden fits take DPB start values from it.

## Start values

Loading an S file on the desktop overwrites the DPB sliders with the prediction, if a net matches the temperature span. If none matches, the sliders keep what they hold: the defaults in a fresh session, or otherwise the previous file's prediction or Adjust to fit values.

A fresh session is the only reproducible state, so cases with no net record the slider defaults, and `start_value_source` says which rule applies.

## Cases

| Case                     | Kind      | Purpose                                                                                                    |
| ------------------------ | --------- | ---------------------------------------------------------------------------------------------------------- |
| `01_Fe2VAl09Si01`        | example   | selects the 400 to 700 K net, with negative Seebeck                                                        |
| `02_SiP`                 | example   | selects no net, because the data cover 308 to 650 K                                                        |
| `03_AWI32_SI`            | example   | selects the 200 to 500 K net                                                                               |
| `01_reversed_rows`       | derived   | selects no net, because selection reads the first and last rows. Shows the behaviour that P9 fixes         |
| `03_negated_seebeck`     | derived   | shows the transform for negative Seebeck                                                                   |
| `synthetic_<low>_<high>` | synthetic | covers all five nets. The data are synthetic straight lines, so their predictions have no physical meaning |

Each case with a selected net records these steps:

- `interpolated_seebeck_v_per_k`: Seebeck at 7 points across the net's range, from a degree-5 fit.
- `network_input_mv_per_k`: those values in mV/K, with the sign flipped when the first three are negative on average.
- `network_output`: the normalised output, between -1 and 1, in float32.
- `reversed_norm`: the output in physical units, computed in float64.
- `prediction`: the same after the transform for negative Seebeck.
- `desktop_start_values`: the prediction after the desktop's slider rounding and range limits.

The last four use `m_eff`, `band_gap_k` and `fermi_energy_k` where they hold those quantities. On the synthetic cases, the limits change some values: for example, a predicted gap of 52464 K becomes 3000 K.

## Regenerating

The script needs a clean SeeBand checkout at commit `803b0e7` and TensorFlow, which is not part of the project setup. It stops on any other commit or on local changes. Run this from the repository root, with SeeBand next to this repository. The environment stays outside the repository:

```sh
uv venv --python 3.11 ../seeband-tf-env
uv pip install --python ../seeband-tf-env/bin/python tensorflow==2.15.1 numpy==1.26.4 h5py==3.16.0
../seeband-tf-env/bin/python packages/seeband_core/scripts/capture_neural_net_references.py \
  --desktop ../SeeBand \
  --output packages/seeband_core/tests/fixtures/neural_net_references.json
```

The fixture is excluded from Prettier and holds the exact script output, so any change to a number shows in the diff. Two runs gave byte-identical files with the versions recorded in the fixture.

The files were saved with Keras 2.9, and these references were captured with TensorFlow 2.15.1 and Keras 2.15.0 on one Mac on Apple Silicon. The original 2.9 environment was not tested, and the desktop GUI was not run: slider rounding and limits are reproduced from `NeuralNetPredictionThread`.

## Numpy port

`seeband_core.neural_nets` runs the same nets with numpy, and `tests/test_neural_nets.py` compares each step with these references. It returns `NeuralNetGuess`, with the chosen range and the prediction, or `NoNeuralNet`.

| Step                                                      | Rule                                                             | Largest difference on one Mac                               |
| --------------------------------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------- |
| Interpolated Seebeck and network input                    | relative difference of at most 1e-9                              | 4.2e-15                                                     |
| Network output                                            | absolute difference of at most 5e-7                              | 1.2e-7, about one float32 step                              |
| `reversed_norm` and `prediction` from the recorded output | relative difference of at most 1e-12                             | exact                                                       |
| Final prediction                                          | relative difference of at most 1e-5, plus 1e-3 in absolute terms | m_eff 2.4e-6, band gap 0.056 K on 52464 K, 5e-4 K on -3.4 K |

The output is rounded in float32, and the inverse transform enlarges this as the output nears 1. That is why the final prediction needs a wider rule than the output. The desktop's slider rounding and limits are not part of this module.

The port keeps the desktop's behaviour:

- It chooses a net from the first and last rows, which P9 fixes.
- An output of exactly 1 gives infinity, not an error.
- It computes the inverse transform in float64, as the desktop does with numpy 1.26. With numpy 2, the desktop's expressions would stay in float32, so the port converts explicitly.

One difference: if the Seebeck fit fails, the port raises `ValueError`, while the desktop fails later with `TypeError`.

## Exporting the weights

`src/seeband_core/data/neural_nets/` holds one `.npz` file per net, exported from the desktop's H5 files. The script stops if a net differs from the expected layers: 7 inputs, dense layers of 16, 16, 8 and 3 units, LeakyReLU with slope 0.1, and tanh at the output. Two runs gave byte-identical files, and `test_weights_are_unchanged` pins their hashes. Run this with the same environment and checkout as above:

```sh
../seeband-tf-env/bin/python packages/seeband_core/scripts/export_neural_net_weights.py \
  --desktop ../SeeBand \
  --output packages/seeband_core/src/seeband_core/data/neural_nets
```
