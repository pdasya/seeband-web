# ruff: noqa: T201 -- print replay results for reviewers.
import math


# Dimensionless x=E/(kBT), mu=0, valence edge=0; equal spectral prefactors.
# Sigma(x)=(-x)^beta Theta(-x)+(x-g)^beta Theta(x-g), beta=1.
def moments(g, n=16000, cutoff=80):
    h = cutoff / n
    result = []
    for power in range(3):
        vals = []
        for i in range(n + 1):
            y = i * h
            a = -y
            b = g + y
            wa = math.exp(a) / (1 + math.exp(a)) ** 2
            wb = math.exp(-b) / (1 + math.exp(-b)) ** 2
            f = y * ((a**power) * wa + (b**power) * wb)
            vals.append(f * (1 if i in (0, n) else (4 if i % 2 else 2)))
        result.append(math.fsum(vals) * h / 3)
    return result


def observables(g, n=16000, cutoff=80):
    j0, j1, j2 = moments(g, n, cutoff)
    return j0, -j1 / j0, j2 - j1 * j1 / j0, (j2 / j0 - (j1 / j0) ** 2)


ref = observables(10)
print("g sigma/sigma10 |S|/|S10| kappa/kappa10 L/L10")
maxerr = 0
for g in range(4, 11):
    vals = observables(g)
    ratios = [v / r for v, r in zip(vals, ref, strict=False)]
    print(g, *(f"{x:.9f}" for x in ratios))
    fine = observables(g, n=32000, cutoff=80)
    wider = observables(g, n=40000, cutoff=100)
    maxerr = max(
        maxerr,
        max(abs(x / y - 1) for x, y in zip(vals, fine, strict=False)),
        max(abs(x / y - 1) for x, y in zip(fine, wider, strict=False)),
    )
    # Exact integration-by-parts sigma check for beta=1.
    expected = math.log(2) + math.log1p(math.exp(-g))
    assert abs(vals[0] - expected) < 2e-12
print("maximum relative change after h halving / cutoff extension", maxerr)
print("reference observables in dimensionless units", ref)

# Compare the independently integrated ratios against the explicit DPB exports.
import csv  # noqa: E402
from pathlib import Path  # noqa: E402

with (Path(__file__).resolve().parent / "model.csv").open() as stream:
    records = [row for row in csv.DictReader(stream) if float(row["gap_kbt"]).is_integer()]
errors = []
for row in records:
    values = observables(float(row["gap_kbt"]))
    errors.extend(
        abs(value / reference - float(row[name + "_ratio"]))
        for name, value, reference in zip(("sigma", "S", "kappa", "L"), values, ref, strict=False)
    )
print("max absolute difference vs explicit DPB for 28 normalized values", max(errors))
assert len(errors) == 28 and max(errors) < 1e-9
