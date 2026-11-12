# Input data

`data_parser.parse_table` reads measured data from text, as separate files or as one table, following the Conventions page of the design.

## Format

- Columns are separated by spaces, tabs or a comma with any spaces around it. A comma at the end of a line is ignored.
- Numbers use a decimal point. `300,5 1,2` is an error, because it looks like decimal commas. `300,5` alone reads as T = 300 and a value of 5.
- Blank lines and anything after `#` are skipped. Line numbers count every line, as an editor does.
- Each column is read in a unit, and measurements come out in SI: K, V/K, Ω·m and m³/C. The unit is the one a user chose for the column, or else the one its header names, or else SI.

## Units

| Quantity | Units (`Unit`)               | Factor to SI      |
| -------- | ---------------------------- | ----------------- |
| T        | `K`, `C` (°C)                | 1; °C adds 273.15 |
| S        | `V/K`, `uV/K`                | 1, 1e-6           |
| ρ        | `Ohm*m`, `mOhm*cm`, `uOhm*m` | 1, 1e-5, 1e-6     |
| R_H      | `m^3/C`, `cm^3/C`            | 1, 1e-6           |

`UNITS` holds this table as a power of ten and an offset for each unit, and `to_si` applies it in decimal, to the value as written, with one rounding. So `50.1` in µV/K gives the very float that `5.01e-5` in V/K does, and `26.85` °C that of `300` K. A float product would not: `50 * 1e-6` is `4.9999999999999996e-05`, and a fit turns that last bit into differences of about 1e-8 in its parameters. A fit from the same data in µV/K and mΩ·cm equals the fit from SI exactly. `ParsedTable.units` gives the unit each mapped column was read in, and `columns` keeps the values as written, for a preview.

A header's unit is read in any usual spelling: spaces, `*`, `·` and `^` do not matter, `µ`, `μ` and `u` are the same, `Ω` is `Ohm`, and `³` is `3`. So `S (µV/K)`, `rho (mΩ·cm)` and `RH (cm³/C)` read in those units. Case does matter for a leading `M`, as mega is not milli: `MOhm cm` is not read as `mOhm cm`.

A unit chosen for a column that its quantity cannot have, such as `cm^3/C` for S, is the error `unit_not_allowed`, and nothing is read.

### A unit that looks wrong

The largest |value| of each quantity, in SI, outside these limits gives the warning `implausible_magnitude` on its column. The values are still read as written.

| Quantity | Limits            |
| -------- | ----------------- |
| S        | 1e-7 to 1e-2 V/K  |
| ρ        | 1e-10 to 1 Ω·m    |
| R_H      | 1e-13 to 0.1 m³/C |

This catches µV/K read as V/K, which is 1e6 too large. It does not catch every wrong unit: the `02_SiP` example reaches ρ = 0.16 Ω·m and |R_H| = 0.013 m³/C, so a resistivity in mΩ·cm or a Hall coefficient in cm³/C read as SI can look possible. For those, only the unit chosen for the column protects the result.

## Headers

Any lines before the first row of numbers are text, and the last of them is the header. A line is text if a field does not start like a number, so a typo such as `3O0 1e-6` is an error on its line and does not become a header.

| Quantity | Recognised headers  | Unit in brackets, if given |
| -------- | ------------------- | -------------------------- |
| T        | T, T_K, temp        | K, °C (also C, degC, ℃)    |
| S        | S, seebeck          | V/K                        |
| ρ        | rho, ρ, resistivity | Ohm m, Ω·m                 |
| R_H      | RH, R_H, hall       | m^3/C, m³/C                |

Names are matched without regard to case, except `T` and `S`: lower-case `t` and `s` usually mean time and a standard deviation.

Where it is not clear what a column holds, the parser leaves it unassigned, because a wrong guess gives numbers that look fine. A user assigns it with `with_mapping`, or by passing `mapping` to `parse_table`.

- A column with a unit in brackets that the parser cannot read, such as `S (mV/K)`, is not assigned, because its values would be wrong by a factor. Assigning it by hand reads it in SI, or in the unit chosen for it, and the warning becomes `unit_assumed`.
- A column assigned by hand keeps a unit its header names, such as `Svalues (uV/K)`.
- A file with no header takes its first column as T. With two columns, the second is the quantity passed as `expected`. With more, the rest are not assigned. `headers` is then left out, and the web app asks the user what the columns hold before using it (D28).
- A header with a different number of columns from the data gives no assignments.

## Problems

Problems are codes, with a line and column where they apply, and no text or measured values. A client translates them. Any error leaves `measurements` empty, and `columns` keeps the rows that could be read, for a preview.

| Code                        | Kind    | Meaning                                                                                             |
| --------------------------- | ------- | --------------------------------------------------------------------------------------------------- |
| `no_data`                   | error   | no row of numbers                                                                                   |
| `wrong_encoding`            | error   | no row of numbers, in a text with NUL or replacement characters, such as UTF-16 read as UTF-8       |
| `line_too_long`             | error   | a line over 2000 characters                                                                         |
| `too_many_problems`         | error   | the list stopped at the line that reached 50 errors                                                 |
| `too_few_columns`           | error   | a line with one number                                                                              |
| `wrong_column_count`        | error   | a line with a different number of columns from the first row                                        |
| `missing_value`             | error   | an empty field, as in `400,,2`                                                                      |
| `not_numeric`, `not_finite` | error   | a value that is not a finite number. `nan` and `inf` are not numeric, and `1e999` is not finite     |
| `decimal_comma`             | error   | a line that looks like it uses decimal commas                                                       |
| `too_few_rows`              | error   | fewer than 2 rows                                                                                   |
| `missing_temperature`       | error   | no column is T. A user can still assign one                                                         |
| `non_positive_temperature`  | error   | T of 0 K or below, after conversion, so -50 °C is fine and -300 °C is not                           |
| `negative_resistivity`      | error   | a resistivity below 0, which no measurement gives (D28)                                             |
| `repeated_role`             | error   | a mapping that uses a quantity twice                                                                |
| `unit_not_allowed`          | error   | a unit chosen for a column that its quantity cannot have                                            |
| `preamble_skipped`          | warning | a line of text before the header, which is left out                                                 |
| `header_mismatch`           | warning | a header with a different number of columns from the data                                           |
| `unit_differs`              | warning | a column with a unit the parser cannot read, which is not assigned                                  |
| `unit_assumed`              | warning | a column with such a unit that a user assigned, read in SI or the unit chosen for it                |
| `implausible_magnitude`     | warning | the largest value of a quantity is outside the limits above, which suggests a wrong unit            |
| `repeated_header`           | warning | a second column for one quantity, which is not assigned                                             |
| `columns_need_assigning`    | warning | more than two columns with no header                                                                |
| `expected_not_found`        | warning | the `expected` quantity is not among the assigned columns                                           |
| `no_quantity`               | warning | no column holds a quantity, so there are no measurements                                            |
| `few_rows`                  | warning | fewer than 6 distinct temperatures, which leaves the degree 5 fit for DPB start values undetermined |
| `unsorted_temperature`      | warning | rows were not in order of T, so `measurements` is sorted. `columns` keeps the order of the text     |
| `duplicate_temperature`     | warning | a repeated T, which stays in place                                                                  |

`01_Fe2VAl09Si01_hall.txt` from the desktop examples measures 100 K twice, so this warning appears on real data.

## Differences from the desktop

D22 records these. In the desktop's parser:

- A line it reads badly can be dropped without a word, such as `-300 1`, or can read wrongly, such as `400` becoming T = S = 400. `400 nan` passes through as NaN.
- Two spaces, double tabs, a comma and a space, a trailing comma, or three columns make the whole file fail.

Here, any line it cannot read is an error with its line number, and those separators work. Three or more columns read, but stay unassigned. Sorting changes which neural net an unsorted file gets, as P9 intends.

## Example files

`tests/fixtures/examples` holds the 9 example files from SeeBand, byte for byte, matching the hashes in the golden results. `NOTICE` records where they come from. SeeBand's license covers its software and documentation, and it does not say whether that includes these measurements or where they come from, so the authors should confirm this (P1).
