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

The script needs a clean SeeBand checkout at commit `803b0e7` and TensorFlow, which is not part of the project setup. It stops on any other commit or on local changes. Use a separate environment:

```sh
uv venv --python 3.11 tf-env
uv pip install --python tf-env/bin/python "tensorflow==2.15.*" h5py
tf-env/bin/python packages/seeband_core/scripts/capture_neural_net_references.py \
  --desktop ../SeeBand \
  --output packages/seeband_core/tests/fixtures/neural_net_references.json
```

The fixture is excluded from Prettier and holds the exact script output, so any change to a number shows in the diff. Two runs gave byte-identical files with the versions recorded in the fixture.

The files were saved with Keras 2.9, and these references were captured with TensorFlow 2.15.1 and Keras 2.15.0 on one Mac on Apple Silicon. A one-off numpy forward pass from the weight files differed from these outputs by at most 1.2e-7. The numpy port makes this check repeatable. The original 2.9 environment was not tested, and the desktop GUI was not run: slider rounding and limits are reproduced from `NeuralNetPredictionThread`.
