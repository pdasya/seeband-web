"""Invert the source dotted curves and predict the solid ordinate at the same energy.
Run with the original Thesberg PDF as first argument, next to crosscheck.py.
Only intersections on displayed path segments are retained.
"""

import csv

import crosscheck as pdf
import numpy as np

output = []
for t in (300, 850):
    full, weighted = (153, 154) if t == 300 else (155, 156)
    x, y = np.array(pdf.points(weighted)).T
    y = 1.5 + (y - pdf.c_ly0) / (pdf.c_ly1 - pdf.c_ly0)
    for row in pdf.rows:
        if row["panel"] != "5c" or row["style"] != "dotted" or row["temperature_k"] != t:
            continue
        target = row["fig6_lorenz_1e8"]
        for i in range(len(x) - 1):
            if (target - y[i]) * (target - y[i + 1]) > 0 or y[i] == y[i + 1]:
                continue
            cx = x[i] + (x[i + 1] - x[i]) * (target - y[i]) / (y[i + 1] - y[i])
            ef = -0.4 + 0.2 * (cx - pdf.c_ex0) / (pdf.c_ex1 - pdf.c_ex0)
            ordinate = pdf.slice_at(full, cx)
            v = None if ordinate is None else 1.5 + (ordinate - pdf.c_ly0) / (pdf.c_ly1 - pdf.c_ly0)
            bx = pdf.b_ex0 + (ef + 0.2) * (pdf.b_ex1 - pdf.b_ex0) / 0.2
            coarse = pdf.slice_at(115 if t == 300 else 119, bx)
            original = next(
                r["fig6_lorenz_1e8"]
                for r in pdf.rows
                if r["panel"] == "5c"
                and r["temperature_k"] == t
                and r["style"] == "solid"
                and r["color"] == row["color"]
            )
            output.append(
                dict(
                    T=t,
                    p20=row["p_cm3"] / 1e20,
                    fig6_dotted=target,
                    fig5_inferred_mu_eV=ef,
                    fig5c_solid=v,
                    fig5b_solid=None
                    if coarse is None
                    else (coarse - pdf.b_ly0) * 30 / (pdf.b_ly1 - pdf.b_ly0),
                    fig6_solid=original,
                )
            )
with (pdf.OUT / "inverse.csv").open("w") as fp:
    w = csv.DictWriter(fp, fieldnames=output[0])
    w.writeheader()
    w.writerows(output)
