# Changelog

## Unreleased

- Added single Kane band (`skb`) joint fitting of S(T), rho(T) and R_H(T), with
  E(k), chemical potential, Lorenz number, eta, density, mobility, Hall factor and
  mass charts. Assumptions: acoustic phonons, constant fully ionized density,
  fixed user-supplied gap and valley count. SPB/DPB golden results are unchanged.
  See [model equations and validation](packages/seeband_core/docs/kane-model.md).

- Integrated SKB into `band_models._BandModel`, reusing signed `band_mass`,
  `fermi_energy`, `A`, N1, scales, curve names, bounds and result handling.
  Density and mobility are derived; the only new parameter is `kane_gap_ev`.
  Verified that the parameter conversion preserves the initial SKB curves and
  approaches SPB with the same acoustic normalization in the parabolic limit.
