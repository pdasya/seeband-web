# Input data

`data_parser.parse_table` reads measured data from text, as separate files or as one table, following the Conventions page of the design.

## Format

- Columns are separated by spaces, tabs or commas, in any amount. A comma at the end of a line is ignored.
- Numbers use a decimal point. `300,5 1,2` is an error, because it looks like decimal commas.
- Blank lines and lines starting with `#` are skipped. Line numbers in problems still count them.
- Values are in K, V/K, Ω·m and m³/C. The parser never converts them.

## Headers

A first line with anything that is not a number is a header. Names are matched without regard to case, and a unit in brackets is ignored, with a `unit_not_checked` warning, because the values are still read in the units above.

| Quantity | Recognised headers  |
| -------- | ------------------- |
| T        | T, T_K, temp        |
| S        | S, seebeck          |
| ρ        | rho, ρ, resistivity |
| R_H      | RH, R_H, hall       |

Unrecognised columns stay out of the suggested mapping, and `to_measurements` takes a mapping a user chose. A file with no header takes its first column as T, and its second as the quantity passed as `expected`.

## Problems

Problems are codes, with a line and column where they apply, and no text or measured values. A client translates them.

| Code                        | Kind    | Meaning                                                                                         |
| --------------------------- | ------- | ----------------------------------------------------------------------------------------------- |
| `no_data`                   | error   | nothing to read, or only a header                                                               |
| `too_few_columns`           | error   | a line with one number                                                                          |
| `wrong_column_count`        | error   | a line with a different number of columns from the first                                        |
| `not_numeric`, `not_finite` | error   | a value that is not a finite number. `nan` and `inf` are not numeric, and `1e999` is not finite |
| `decimal_comma`             | error   | a line that looks like it uses decimal commas                                                   |
| `too_few_rows`              | error   | fewer than 2 rows                                                                               |
| `missing_temperature`       | error   | no column is T. A user can still assign one                                                     |
| `non_positive_temperature`  | error   | T of 0 K or below                                                                               |
| `repeated_role`             | warning | a second column for the same quantity, which is left out                                        |
| `unit_not_checked`          | warning | a header gives a unit, which is not converted                                                   |
| `few_rows`                  | warning | fewer than 6 rows, which leaves the degree 5 fit for DPB start values undetermined              |
| `unsorted_temperature`      | warning | rows were not in order of T, and are now sorted                                                 |
| `duplicate_temperature`     | warning | a repeated T, which stays in place                                                              |

`01_Fe2VAl09Si01_hall.txt` from the desktop examples measures 100 K twice, so this warning appears on real data.

## Differences from the desktop

D22 records these. The desktop drops lines it cannot read without saying so, and fails on two spaces or a comma and a space. Here, a bad line is an error, and those separators work. Sorting changes which neural net an unsorted file gets, as P9 intends.

The examples in `tests/fixtures/examples` come from SeeBand, under its license, and match the hashes in the golden results.
