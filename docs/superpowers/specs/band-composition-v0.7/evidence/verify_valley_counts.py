"""Execute with PYTHONPATH=scripts from the PR checkout. Check the design reference inputs."""

from functools import partial

from verify_band_composition_design import Band as ChargeBand
from verify_mixed_scattering_design import Band as MixedBand
from verify_skb_design_reference import kane, velocity_dos
from verify_spb_design_coefficients import closed, momentum

references = (
    partial(ChargeBand, 1, 0, 1),
    partial(MixedBand, 1, 0, 1, crossover_k=0),
    partial(closed, 0, 300, 1, 1, law="acPh"),
    partial(momentum, 0, 300, 1, 1, law="acPh"),
    partial(kane, 0, 300, 1, 1, epsilon=0),
    partial(velocity_dos, 0, 300, 1, 1, epsilon=0),
)
for reference in references:
    for invalid_count in (1.1, "1.1", "1,1", 0, -1, True, None):
        try:
            reference(valleys=invalid_count)
        except ValueError as error:
            assert "positive integer" in str(error)
        else:
            raise AssertionError(f"{reference.func.__name__} accepted {invalid_count!r}")
    reference(valleys=2)
print("6 design references: 42 invalid valley inputs rejected; N=2 accepted by all.")  # noqa: T201
