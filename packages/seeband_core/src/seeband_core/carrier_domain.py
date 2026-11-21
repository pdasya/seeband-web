"""Coordinate limits for the explicit T=0 Fermi-energy carrier branch.

These are admissibility limits, not researcher-selected fit bounds. Energies are
in kelvin; masses are positive single-valley masses and N1/N2 count valleys.
"""

from math import exp, inf, isfinite, log

from seeband_core.model_interface import BandConfiguration, CarrierType

CarrierDomain = tuple[float | None, float | None, bool]
_EMPTY: CarrierDomain = (inf, -inf, True)


def _exp(value: float) -> float:
    """An out-of-float-range boundary represents an unbounded coordinate limit."""
    try:
        return exp(value)
    except OverflowError:
        return inf


def carrier_domain(
    name: str,
    configuration: BandConfiguration,
    carrier_type: CarrierType,
    ef_k: float,
    offset_k: float,
    mass_ratio: float,
    n1: float,
    n2: float,
) -> CarrierDomain | None:
    """Return lower/upper limits and endpoint inclusion at fixed other coordinates.

    ``None`` means unrestricted. A reversed interval is empty. Callers request
    offset/mass limits only with a manually fixed Fermi energy. Either carrier
    branch includes compensation for mixed bands; same-type occupancy is strict.
    """
    if not all(isfinite(value) for value in (ef_k, offset_k, mass_ratio, n1, n2)):
        raise ValueError("Carrier limits require finite energies, mass ratio and valleys")
    if mass_ratio <= 0 or n1 <= 0 or n2 <= 0:
        raise ValueError("Carrier limits require positive mass ratio and valleys")
    if configuration not in ("cb_cb", "vb_vb", "vb_cb") or carrier_type not in ("n", "p"):
        raise ValueError("Unknown band configuration or carrier type")
    if name not in ("fermi_energy", "band_offset_k", "mass_ratio"):
        return None
    if configuration != "vb_cb":
        conduction = configuration == "cb_cb"
        if (carrier_type == "n") != conduction:
            return _EMPTY
        if name == "fermi_energy":
            return (
                (min(0.0, offset_k), None, False)
                if conduction
                else (None, max(0.0, offset_k), False)
            )
        if name == "band_offset_k":
            if conduction and ef_k <= 0:
                return (None, ef_k, False)
            if not conduction and ef_k >= 0:
                return (ef_k, None, False)
        if name == "mass_ratio" and (
            (conduction and ef_k <= min(0.0, offset_k))
            or (not conduction and ef_k >= max(0.0, offset_k))
        ):
            return _EMPTY
        return None

    # b/a = M (N2/N1)^(2/3). Absolute mass and the DOS density scale cancel.
    log_valley_ratio = (2 / 3) * (log(n2) - log(n1))
    log_ratio = log(mass_ratio) + log_valley_ratio
    if name == "fermi_energy":
        # b/(a+b) without overflowing relative masses or valley multiplicities.
        fraction = (
            1 / (1 + exp(-log_ratio)) if log_ratio >= 0 else exp(log_ratio) / (1 + exp(log_ratio))
        )
        neutral = (
            (offset_k if carrier_type == "p" else 0.0) if offset_k >= 0 else offset_k * fraction
        )
        return (None, neutral, True) if carrier_type == "p" else (neutral, None, True)
    if name == "band_offset_k":
        boundary = ef_k * (1 + _exp(-log_ratio)) if ef_k < 0 else ef_k
        if carrier_type == "p":
            return (boundary, None, True)
        return (None, boundary, True) if ef_k < 0 else None

    if offset_k < ef_k < 0:
        boundary = _exp(log(-ef_k) - log(ef_k - offset_k) - log_valley_ratio)
        return (None, boundary, True) if carrier_type == "p" else (boundary, None, True)
    # A positive mass cannot reverse the excess from a single occupied pocket.
    if (carrier_type == "p" and ef_k >= 0 and ef_k > offset_k) or (
        carrier_type == "n" and ef_k < 0 and ef_k <= offset_k
    ):
        return _EMPTY
    return None
