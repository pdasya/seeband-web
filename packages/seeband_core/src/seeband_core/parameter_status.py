"""How a fit found each parameter (R7), from the signals the fit already has.

A fit that ends normally still says nothing about whether the data determine a parameter. These
statuses say what the fit can tell, and no more:

- `held`: the request held it at its start value.
- `fixed`: the fit mode does not fit it, or it belongs to another scattering type.
- `not_assessed`: the fit failed, or ended before the stage that fits it, as a stopped Hall fit
  never reaches m1.
- `at_bound`: it ended at a bound, which may be what set it.
- `not_determined`: the data do not depend on it. Either the solver saw no effect of it on its
  data (a stage error of exactly 0 or not finite, or an unidentified parameter of the verified
  method), or it is the DPB Fermi energy inside the gap with m_eff > 0, where both bands are empty
  at 0 K for any value in the gap, so μ(T), and so S, ρ and R_H, are the same for each.
- `did_not_move`: it ended within `DID_NOT_MOVE_TOLERANCE`, relative, of its start.
- `estimated`: none of the above. This does not mean that the data determine it well, or that it
  is right; its uncertainty is not assessed (#182).

The first that applies, in this order, is the status.
"""

from collections.abc import Collection, Mapping

from seeband_core.model_interface import FitMode, FitStatus, ParameterStatus

# A value closer than this to its start, relative to the larger of |start| and 1, did not move.
DID_NOT_MOVE_TOLERANCE = 1e-9


def parameter_statuses(
    fit_mode: FitMode,
    scattering: str | None,
    start: Mapping[str, float],
    parameters: Mapping[str, float],
    *,
    status: FitStatus,
    held: Collection[str],
    at_bounds: Collection[str],
    undetermined: Collection[str],
    reached: Collection[str] | None,
) -> dict[str, ParameterStatus]:
    """The status of each parameter in `parameters`. `reached` None means every fitted one."""
    active = {spec.name for spec in fit_mode.parameters_for(scattering)}
    statuses: dict[str, ParameterStatus] = {}
    for spec in fit_mode.parameters:
        name = spec.name
        if name not in parameters:
            continue
        if name in held:
            statuses[name] = "held"
        elif spec.role != "fitted" or name not in active:
            statuses[name] = "fixed"
        elif status == "failed" or (reached is not None and name not in reached):
            statuses[name] = "not_assessed"
        elif name in at_bounds:
            statuses[name] = "at_bound"
        elif name in undetermined or _fermi_energy_in_gap(fit_mode, name, parameters):
            statuses[name] = "not_determined"
        elif _did_not_move(parameters[name], start.get(name)):
            statuses[name] = "did_not_move"
        else:
            statuses[name] = "estimated"
    return statuses


def _fermi_energy_in_gap(fit_mode: FitMode, name: str, parameters: Mapping[str, float]) -> bool:
    """The DPB carrier density at 0 K is 0 for any E_F strictly inside the gap with m_eff > 0.

    Band 1 holds holes only for E_F < 0, and band 2, a conduction band for m_eff > 0, holds
    electrons only for E_F > E_g. With neither, the density balance has the same target, 0, for
    each such E_F, so the solved μ(T) and every curve are the same to the last bit, as
    `tests/test_parameter_status.py` checks.
    """
    if name != "fermi_energy" or not fit_mode.id.startswith("dpb"):
        return False
    mass, gap, energy = (parameters.get(key) for key in ("m_eff", "band_gap", "fermi_energy"))
    if mass is None or gap is None or energy is None:
        return False
    return mass > 0 and 0 < energy < gap


def _did_not_move(value: float, start: float | None) -> bool:
    if start is None:
        return False
    return abs(value - start) <= DID_NOT_MOVE_TOLERANCE * max(abs(start), 1.0)
