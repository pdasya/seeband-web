# Curve availability

Which curves each mode offers through `POST /api/calc`, from the desktop's additional graphs windows. Availability does not depend on scattering. SPB S + ρ + R_H is listed, but the mode is disabled, so the API refuses all its curves until #83.

| Kind                              | SPB S               | SPB S + ρ, S + ρ + R_H | DPB S               | DPB S + ρ     | DPB S + ρ + R_H |
| --------------------------------- | ------------------- | ---------------------- | ------------------- | ------------- | --------------- |
| `measured`                        | yes                 | yes                    | yes                 | yes           | yes             |
| `seebeck`                         | `same_as_measured`  | `same_as_measured`     | `same_as_measured`  | yes           | yes             |
| `seebeck_by_band`                 | `single_band`       | `single_band`          | yes                 | yes           | yes             |
| `chemical_potential`              | yes                 | yes                    | yes                 | yes           | yes             |
| `electrical_conductivity`         | `needs_resistivity` | yes                    | `needs_resistivity` | yes           | yes             |
| `electrical_conductivity_by_band` | `single_band`       | `single_band`          | `needs_resistivity` | yes           | yes             |
| `thermal_conductivity`            | `needs_resistivity` | yes                    | `needs_resistivity` | yes           | yes             |
| `carrier_concentration_by_band`   | `not_on_desktop`    | `not_on_desktop`       | yes, relative       | yes, relative | yes, absolute   |

`thermal_conductivity` is the electronic part only, κ_e, with the bipolar term in DPB. There is no lattice term, on the desktop or here.

`seebeck` is a separate call on the desktop in DPB S + ρ and S + ρ + R_H, where it gives exactly the S of `measured`, in every run compared here. `same_as_measured` marks the modes with no such call.

## Relative and absolute n

Carrier concentration scales with m1^1.5, where m1 is the mass of band 1, and only R_H can set it. DPB S and S + ρ use m1 = 1, as on the desktop, so their n is **relative**: its size rests on that assumption.

In DPB S + ρ + R_H, n uses the m1 it is given, and the mode reports it as **absolute**. That describes the mode, not the value: at the default m1 = 1, before a fit, n equals the relative one.

**This n from a fit is too low, by about 2 in the single-band limit,** as R_H is wrong by that factor. `dpb_hall_prefactor` flags it until #81.

## The sign of n

Band 1 is a valence band, so its n is negative. Band 2 takes the sign of `m_eff`, so with `m_eff` below 0 both are negative. So n has the opposite sign to R_H: R_H · n · e comes out as -0.50 in the single-band limit, on both sides. Its size is the error of #81, and a physicist should confirm the sign convention.

m1 below 0 gives complex values, which the API refuses with `calculation_failed`. m1 = 0 gives an n of 0.

## Known errors in these curves

With `acPhDis`, `seebeck_by_band`, `electrical_conductivity`, `electrical_conductivity_by_band` and `thermal_conductivity` are **wrong**, and `acphdis_curve_scale` flags them until #82: σ · ρ is not 1, and the band contributions to S need not sum to S.

## Differences from the desktop

- **One button, two kinds.** The desktop's Seebeck coefficient and Electrical conductivity buttons in DPB draw each band and the total together. Here those are separate kinds. In DPB S, the total is `measured`.
- **Unit of n.** The desktop multiplies n by 1e6 for its graph, which gives m⁻³. Curves here keep the core's cm⁻³, as their names say.
- **Values after a fit.** The desktop's buttons read the sliders, not the fit. Until "Adjust to fit" is pressed, a graph uses the old values, and after it they are cut to slider steps. Here a curve uses the exact values it is given. So in every scattering type, a curve at fitted values can differ from the desktop's graph.
- **Scale of C and D (D20).** At one slider position, with `acPhDis`, the desktop's buttons use C and D 100 times apart from a fit's start. Here a curve uses core units. V1 records it.
- **Grid.** The desktop always uses 50 points. Here `points` is a choice, with 50 as the default.
- **Print to file** on the desktop is export, which belongs to R4, including the extra row at T = 0 in its chemical potential file.
