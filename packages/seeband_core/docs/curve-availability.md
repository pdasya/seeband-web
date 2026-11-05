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

## Relative and absolute n

Carrier concentration needs the mass m1 of band 1, and only R_H sets it. DPB S and S + ρ use m1 = 1, as on the desktop, so their n is **relative**: its size rests on that assumption. In DPB S + ρ + R_H, n comes from the fitted m1, and is **absolute**, though it carries the flag `dpb_hall_prefactor` until #81. Band 1 is a valence band, so its n is negative.

## Differences from the desktop

- **One button, two kinds.** The desktop's Seebeck coefficient and Electrical conductivity buttons in DPB draw each band and the total together. Here those are separate kinds. In DPB S, the total is `measured`.
- **Unit of n.** The desktop multiplies n by 1e6 for its graph, which gives m⁻³. Curves here keep the core's cm⁻³, as their names say.
- **Scale of C and D (D20).** The desktop's buttons read C and D from the sliders at other scales than a fit uses, so with `acPhDis` its graphs use values 100 times apart from the fit. Here a curve uses the values it is given, in core units. So with `acPhDis` these curves differ from the desktop's, and V1 records it.
- **Grid.** The desktop always uses 50 points. Here `points` is a choice, with 50 as the default.
- **Print to file** on the desktop is export, which belongs to R4.
