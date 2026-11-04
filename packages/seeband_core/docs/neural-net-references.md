# Neural net references

[`neural_net_references.json`](../tests/fixtures/neural_net_references.json) records the outputs of the SeeBand desktop neural nets. The numpy port compares against it, and golden fits take DPB start values from it, because loading an S file on the desktop overwrites the DPB sliders with the prediction.

## Cases

| Case                     | Kind      | Purpose                                                                                                    |
| ------------------------ | --------- | ---------------------------------------------------------------------------------------------------------- |
| `01_Fe2VAl09Si01`        | example   | selects the 400 to 700 K net, with negative Seebeck                                                        |
| `02_SiP`                 | example   | selects no net, because the data cover 308 to 650 K                                                        |
| `03_AWI32_SI`            | example   | selects the 200 to 500 K net                                                                               |
| `01_reversed_rows`       | derived   | selects no net, because selection reads the first and last rows. Shows the behaviour that P9 fixes         |
| `03_negated_seebeck`     | derived   | shows the transform for negative Seebeck                                                                   |
| `synthetic_<low>_<high>` | synthetic | covers all five nets. The data are synthetic straight lines, so their predictions have no physical meaning |

Each case with a selected net records the interpolated Seebeck values, network input and output, the denormalised values, the prediction, and the start values after the desktop's slider rounding and range limits. On the synthetic cases, the limits change some values: for example, a predicted gap of 52464 K becomes 3000 K.

## Regenerating

The script needs a SeeBand checkout and TensorFlow, which is not part of the project setup. Use a separate environment:

```sh
uv venv --python 3.11 tf-env
uv pip install --python tf-env/bin/python "tensorflow==2.15.*" h5py
tf-env/bin/python packages/seeband_core/scripts/capture_neural_net_references.py \
  --desktop ../SeeBand \
  --output packages/seeband_core/tests/fixtures/neural_net_references.json
```

The files were saved with Keras 2.9, and these references were captured with TensorFlow 2.15.1 and Keras 2.15.0 on one Mac on Apple Silicon. The exact versions are in the fixture. Two runs gave byte-identical files, and a separate numpy forward pass from the weight files matched the network outputs. The original 2.9 environment was not tested.
