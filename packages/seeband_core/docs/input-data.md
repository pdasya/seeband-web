# Input data

`data_parser.parse_table` reads measured data from text, as separate files or as one table, following the Conventions page of the design.

## Format

- Columns are separated by spaces, tabs or a comma with any spaces around it. A comma at the end of a line is ignored.
- Numbers use a decimal point. `300,5 1,2` is an error, because it looks like decimal commas. `300,5` alone reads as T = 300 and a value of 5.
- Blank lines and anything after `#` are skipped. Line numbers count every line, as an editor does.
- Values are in K, V/K, Ω·m and m³/C. The parser never converts them.

## Headers

Any lines before the first row of numbers are text, and the last of them is the header. A line is text if a field does not start like a number, so a typo such as `3O0 1e-6` is an error on its line and does not become a header.

| Quantity | Recognised headers  | Unit in brackets, if given |
| -------- | ------------------- | -------------------------- |
| T        | T, T_K, temp        | K                          |
| S        | S, seebeck          | V/K                        |
| ρ        | rho, ρ, resistivity | Ohm m, Ω·m                 |
| R_H      | RH, R_H, hall       | m^3/C, m³/C                |

Names are matched without regard to case, except `T` and `S`: lower-case `t` and `s` usually mean time and a standard deviation.

Where it is not clear what a column holds, the parser leaves it unassigned, because a wrong guess gives numbers that look fine. A user assigns it with `with_mapping`, or by passing `mapping` to `parse_table`.

- A column with another unit in brackets, such as `S (uV/K)`, is not assigned, because its values would be wrong by a factor. Assigning it by hand reads it as V/K.
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
| `non_positive_temperature`  | error   | T of 0 K or below                                                                                   |
| `negative_resistivity`      | error   | a resistivity below 0, which no measurement gives (D28)                                             |
| `repeated_role`             | error   | a mapping that uses a quantity twice                                                                |
| `preamble_skipped`          | warning | a line of text before the header, which is left out                                                 |
| `header_mismatch`           | warning | a header with a different number of columns from the data                                           |
| `unit_differs`              | warning | a column with another unit, which is not assigned                                                   |
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
