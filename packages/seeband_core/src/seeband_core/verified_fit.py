"""P19 sequential absolute least squares, sharing the unchanged P13 physical kernels.

The public coordinates (including R=m_eff) are retained throughout. Residuals
are scaled by the historical stage factors, never by sample-dependent weights.
Free inverse amplitudes are eliminated by bounded linear least squares.
"""

from collections import OrderedDict
from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import TypedDict

import numpy as np
from scipy.optimize import least_squares

from seeband_core import math_module as mm
from seeband_core.fit_module import _dpb_branch_bounds
from seeband_core.known_issues import active_issue_ids
from seeband_core.model_interface import (
    QUANTITY_UNITS,
    Bounds,
    FitDiagnostics,
    FitMode,
    FitRequest,
    FitResult,
    FitStatus,
    FitStopped,
    IterationCallback,
    IterationUpdate,
    Quantity,
    ResidualDiagnostics,
)

# sqrt(eps) is the natural relative floor for a least-squares objective audit.
# Fourth-order derivatives use eps**(1/5), independently checked at half-step.
_AUDIT_RTOL = float(np.sqrt(np.finfo(float).eps))
# The stationarity certificate must resolve a smaller derivative error than its
# acceptance threshold. Half-step refinement checks that condition explicitly.
_STATIONARITY_TOL = float(np.finfo(float).eps ** 0.25)
_DERIVATIVE_RTOL = _STATIONARITY_TOL / 4
_MAX_EVALUATIONS = 12000
_SCALE: dict[Quantity, float] = {"seebeck": 1e6, "resistivity": 1e8, "hall": 1e10}


class DerivativeValidationError(ValueError):
    """No admissible step gave independently agreeing derivative estimates."""


class _BudgetReached(Exception):
    pass


class _UnattainedAmplitude(ValueError):
    """The finite user interval has no finite least-squares minimizer."""


class _RootArguments(TypedDict, total=False):
    potentials: np.ndarray


class _CheckedRootProvider:
    """Fit-local exact reuse of successful P8 roots, never of failures.

    At most 32 arrays of 10000 points; keys and roots together use about 5 MB.
    Scalar types, signed zero, temperature dtype and iteration order stay distinct.
    """

    def __init__(self) -> None:
        self._roots: OrderedDict[tuple[object, ...], np.ndarray] = OrderedDict()

    def __call__(
        self,
        model: str,
        t: np.ndarray,
        mass: float,
        ef: float,
        gap: float | None = None,
        degen: float = 1.0,
    ) -> np.ndarray:
        def solve() -> np.ndarray:
            if model == "spb":
                return mm.spb_chemPot_vs_temp(t, mass, ef)
            assert gap is not None
            return mm.dpb_chemPot_vs_temp(t, gap, mass, ef, degen)

        if t.size > 10000:
            return solve()
        scalars = tuple(
            (type(value), np.asarray(value).dtype.str, np.asarray(value).tobytes())
            for value in (mass, ef, gap, degen)
            if value is not None
        )
        key = (model, t.shape, t.dtype.str, t.tobytes(), scalars)
        if key not in self._roots:
            roots = solve().copy()
            roots.setflags(write=False)
            self._roots[key] = roots
            if len(self._roots) > 32:
                self._roots.popitem(last=False)
        self._roots.move_to_end(key)
        return self._roots[key].copy()


def _evaluate_quantity(
    q: Quantity,
    t: np.ndarray,
    p: Mapping[str, float],
    fit_mode: str,
    scattering: str | None,
    degen: float,
    check_finite: bool = True,
    root_provider: _CheckedRootProvider | None = None,
) -> np.ndarray:
    if scattering == "ionized":
        from seeband_core.transport import ionized_transport

        potentials = None
        if root_provider is not None:
            if fit_mode.startswith("dpb"):
                potentials = root_provider(
                    "dpb", t, p["m_eff"] / degen, p["fermi_energy"], p["band_gap"], degen
                )
            else:
                potentials = root_provider("spb", t, p["band_mass"], p["fermi_energy"])
        out = ionized_transport(t, p, fit_mode, degen, potentials=potentials)[q]
        if check_finite and not np.all(np.isfinite(out)):
            raise ValueError("The model gave values that are not finite")
        return out
    dpb = fit_mode.startswith("dpb")
    ef = p["fermi_energy"]
    sc = scattering
    a = p.get("F" if sc == "dis" else "A", 1.0)
    b = p.get("G" if sc == "dis" else "B", 1.0)
    c, d = 300.0 * p.get("C", 0.0), 300.0 * p.get("D", 0.0)
    roots: _RootArguments
    with np.errstate(all="ignore"):
        if dpb:
            r, gap = p["m_eff"] / degen, p["band_gap"]
            roots = (
                {}
                if root_provider is None
                else {"potentials": root_provider("dpb", t, r, ef, gap, degen)}
            )
            if q == "seebeck":
                if fit_mode == "dpb_s":
                    out = mm.dpb_see_vs_temp(t, r, gap, ef, degen, **roots)
                elif sc == "acPhDis":
                    out = mm.dpb_see_vs_temp_double_scatter(t, r, gap, ef, degen, b, c, d, **roots)
                else:
                    out = mm.dpb_see_vs_temp_single_scatter(t, r, gap, ef, degen, b, **roots)
            else:
                f1, f2 = mm.dpb_fermiInt_vs_temp(0, t, r, gap, ef, degen, **roots)
                suffix = {"acPh": "acPh", "dis": "dis", "acPhDis": "acPh_dis"}[str(sc)]
                rho_args = [t, f1, f2, a, b] + ([c, d] if sc == "acPhDis" else []) + [r]
                rho = getattr(mm, "dpb_rho_vs_temp_" + suffix)(*rho_args)
                if q == "resistivity":
                    out = rho
                else:
                    fm1, fm2 = mm.dpb_fermiInt_vs_temp(-0.5, t, r, gap, ef, degen, **roots)
                    args = [t, rho, fm1, fm2, r, degen, a, b]
                    args += ([c, d] if sc == "acPhDis" else []) + [p["m1"] ** 1.5]
                    out = getattr(mm, "dpb_hall_vs_temp_" + suffix)(*args)
        else:
            mass = p["band_mass"]
            root_mass = mass if q == "seebeck" else np.sign(mass)
            root_t = np.asarray(t, dtype=float) if q == "hall" else t
            roots = (
                {}
                if root_provider is None
                else {"potentials": root_provider("spb", root_t, root_mass, ef)}
            )
            if q == "seebeck":
                out = mm.spb_see_vs_temp(t, ef, mass, **roots)
            elif q == "hall":
                out = mm.spb_hall_vs_temp(
                    t, ef, np.sign(mass), -np.sign(mass) * abs(mass) ** 1.5, **roots
                )
            else:
                f = mm.spb_fermiInt_vs_temp(0, t, np.sign(mass), ef, **roots)
                if sc == "acPhDis":
                    out = mm.spb_rho_vs_temp_acPh_dis(t, f, a, c)
                else:
                    out = getattr(mm, "spb_rho_vs_temp_" + str(sc))(t, f, a)
    out = np.asarray(out, dtype=float)
    if check_finite and not np.all(np.isfinite(out)):
        raise ValueError("The model gave values that are not finite")
    return out


class _Coordinates:
    """Numerical coordinates with exact public bounds and fixed mass branches.

    Strictly nonzero masses use log(abs(public mass)); zero-permitted scattering
    shapes remain linear. This adds no mass floor or alternate physical kernel.
    """

    def __init__(
        self, names: list[str], values: Mapping[str, float], bound: Callable[[str], Bounds]
    ) -> None:
        self.names = names
        self.scale = np.array([max(abs(values[n]), 1.0) for n in names])
        self.logarithmic = np.array([n in ("m_eff", "band_mass") for n in names])
        self.sign = np.array([np.sign(values[n]) for n in names])
        self.public_lower = np.array([bound(n).lower for n in names])
        self.public_upper = np.array([bound(n).upper for n in names])
        self.point = self.encode(np.array([values[n] for n in names]))
        with np.errstate(divide="ignore"):
            first, last = self.encode(self.public_lower), self.encode(self.public_upper)
        self.lower, self.upper = np.minimum(first, last), np.maximum(first, last)

    def encode(self, values: np.ndarray) -> np.ndarray:
        result = values / self.scale
        result[self.logarithmic] = np.log(np.abs(values[self.logarithmic]))
        return np.asarray(result)

    def decode(self, z: np.ndarray) -> dict[str, float]:
        values = z * self.scale
        values[self.logarithmic] = self.sign[self.logarithmic] * np.exp(z[self.logarithmic])
        # Restore exact public endpoint values despite exp(log(bound)) rounding.
        values = np.clip(values, self.public_lower, self.public_upper)
        return dict(zip(self.names, values, strict=True))

    def multiply(self, z: np.ndarray, factor: float) -> np.ndarray:
        seed = z * factor
        seed[self.logarithmic] = z[self.logarithmic] + np.log(factor)
        return np.clip(seed, self.lower, self.upper)


def _validated_jacobian(
    evaluate: Callable[[np.ndarray], np.ndarray],
    z: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> np.ndarray:
    """Fourth-order admissible differences, independently checked at half-step.

    Both smaller and larger stencils are tried: shrinking alone amplifies kernel
    evaluation noise. Domain exclusion is distinct from failure of a valid solve.
    """
    f0 = evaluate(z)
    columns = []
    for i in range(len(z)):
        cache: dict[float, np.ndarray | None] = {0.0: f0}

        def at(
            delta: float, i: int = i, cache: dict[float, np.ndarray | None] = cache
        ) -> np.ndarray | None:
            if delta in cache:
                return cache[delta]
            trial = z.copy()
            trial[i] += delta
            if not lower[i] <= trial[i] <= upper[i] or trial[i] == z[i]:
                cache[delta] = None
                return None
            try:
                value = evaluate(trial)
            except mm.NoFiniteChemicalPotentialError:
                value = None
            cache[delta] = value
            return value

        def difference(h: float) -> np.ndarray | None:
            plus, minus, twoplus, twominus = at(h), at(-h), at(2 * h), at(-2 * h)
            if (
                plus is not None
                and minus is not None
                and twoplus is not None
                and twominus is not None
            ):
                return np.asarray((8 * (plus - minus) - (twoplus - twominus)) / (12 * h))
            for direction in (1.0, -1.0):
                values = []
                for k in (1, 2, 3, 4):
                    value = at(direction * k * h)
                    if value is None:
                        break
                    values.append(value - f0)
                if len(values) == 4:
                    return np.asarray(
                        (48 * values[0] - 36 * values[1] + 16 * values[2] - 3 * values[3])
                        / (12 * direction * h)
                    )
            return None

        initial = np.finfo(float).eps ** 0.2 * max(1.0, abs(z[i]))
        steps = [initial]
        for k in range(1, 25):
            if k <= 8:
                steps.append(initial * 2**k)
            steps.append(initial * 2.0 ** (-k))
        for h in steps:
            full, half = difference(h), difference(h / 2)
            if full is None or half is None:
                continue
            error = np.linalg.norm(half - full)
            if error <= _DERIVATIVE_RTOL * max(np.linalg.norm(half), 1e-8):
                columns.append((16 * half - full) / 15)
                break
        else:
            raise DerivativeValidationError("No validated admissible derivative stencil")
    return np.asarray(columns).T


def _projected_optimality(
    jac: np.ndarray, residual: np.ndarray, x: np.ndarray, lower: np.ndarray, upper: np.ndarray
) -> float:
    gradient = jac.T @ residual
    norms = np.linalg.norm(jac, axis=0)
    distance = np.where(gradient > 0.0, x - lower, upper - x)
    projected = np.abs(gradient) * np.minimum(1.0, np.maximum(0.0, distance))
    denominator = norms * max(1.0, float(np.linalg.norm(residual)))
    return float(
        np.max(
            np.divide(projected, denominator, out=np.zeros_like(projected), where=denominator > 0)
        )
    )


class _Engine:
    def __init__(self, request: FitRequest, mode: FitMode) -> None:
        self.request, self.mode = request, mode
        self.dpb = request.fit_mode.startswith("dpb")
        self.n = request.band_2_degeneracy / request.band_1_degeneracy
        self.values = dict(request.start)
        self.specs = {s.name: s for s in mode.parameters_for(request.scattering)}
        self.fitted = {s.name for s in self.specs.values() if s.role == "fitted"}
        self.free = self.fitted - request.held
        self.bounds = {
            name: request.bounds.get(name) or self.specs[name].fit_bounds for name in self.fitted
        }
        self.evaluations = 0
        self.recoveries = 0
        self.optimality: dict[str, float] = {}
        self.objectives: dict[str, float] = {}
        self.iterations = 0
        self.data = {}
        for q in mode.quantities:
            m = request.measurements[q]
            order = np.argsort(m.temperature_k, kind="stable")
            self.data[q] = (m.temperature_k[order], m.values[order])
        # Per-fit cache: at most 32 curves of at most 10000 points (~2.6 MB).
        # Its temperatures, scattering, branch and degeneracy are fixed by this engine.
        self._cached_prediction = lru_cache(maxsize=32)(self._uncached_prediction)
        self._root_provider: _CheckedRootProvider | None = _CheckedRootProvider()
        if not 0 < self.n < np.inf:
            raise ValueError("Band degeneracies must be positive")
        for name in self.fitted:
            b = self.bound(name)
            if not b.lower <= self.values[name] <= b.upper:
                raise ValueError("Start values outside bounds")
        if self.dpb and self.values["m_eff"] == 0:
            raise ValueError("Zero band mass has no finite density domain")
        if not self.dpb:
            mass = self.values["band_mass"]
            if mass == 0:
                raise ValueError("The start band mass is outside the bounds of its carrier branch.")
            if "hall" in self.data and np.sign(np.median(self.data["hall"][1])) == np.sign(mass):
                raise ValueError(
                    "The carrier type of the start band mass contradicts the sign of R_H."
                )

    def bound(self, name: str) -> Bounds:
        b = self.bounds[name]
        assert b is not None
        if name == "m_eff":
            lo, hi = _dpb_branch_bounds(self.request.start[name], ([b.lower], [b.upper]))
            return Bounds(float(lo[0]), float(hi[0]))
        if name == "band_mass":
            if self.request.start[name] < 0:
                return Bounds(b.lower, min(b.upper, 0.0))
            return Bounds(max(b.lower, 0.0), b.upper)
        return b

    def _uncached_prediction(
        self, q: Quantity, parameters: tuple[tuple[str, type[float], float, bool], ...]
    ) -> np.ndarray:
        if self.evaluations >= _MAX_EVALUATIONS:
            raise _BudgetReached
        self.evaluations += 1
        values = _evaluate_quantity(
            q,
            self.data[q][0],
            {name: value for name, _, value, _ in parameters},
            self.mode.id,
            self.request.scattering,
            self.n,
            root_provider=self._root_provider,
        ).copy()
        values.setflags(write=False)
        return values

    def predict(self, q: Quantity, p: Mapping[str, float]) -> np.ndarray:
        """Reuse only exact complete inputs; count physical cache misses, not lookups.

        Copies prevent callers from modifying stored predictions. Larger curves bypass
        the cache, and failed/domain-invalid evaluations are never stored by lru_cache.
        """
        # Preserve scalar type and signed zero as well as the exact numeric value.
        key = tuple(
            (name, type(value), value, bool(np.signbit(value))) for name, value in sorted(p.items())
        )
        prediction = (
            self._cached_prediction(q, key)
            if self.data[q][0].size <= 10000
            else self._uncached_prediction(q, key)
        )
        return prediction.copy()

    def amplitude(self, q: Quantity) -> str | None:
        if q == "resistivity":
            return "F" if self.request.scattering == "dis" else "A"
        if q == "hall":
            return "m1" if self.dpb else "band_mass"
        return None

    def profile(self, q: Quantity, p: dict[str, float]) -> None:
        name = self.amplitude(q)
        if name is None or name not in self.free:
            return
        power = 1.5 if q == "hall" else 1.0
        sign = -1.0 if name == "band_mass" and self.request.start[name] < 0 else 1.0
        shape = self.predict(q, p | {name: sign}) * _SCALE[q]
        data = self.data[q][1] * _SCALE[q]
        norm = float(np.linalg.norm(shape))
        if norm == 0:
            return
        b = self.bound(name)
        small, large = sorted((abs(b.lower), abs(b.upper)))
        if q != "hall" and b.lower < 0:
            raise ValueError("Inverse amplitude bounds must be nonnegative")
        if large <= 0:
            raise _UnattainedAmplitude("Singular amplitude interval")
        low = large ** (-power)
        high = small ** (-power) if small > 0 else np.inf
        # Normalize the shape before its dot product to avoid squaring tiny numbers.
        inverse = float(np.dot(shape / norm, data) / norm)
        inverse = float(np.clip(inverse, low, high))
        if inverse <= 0 or not np.isfinite(inverse):
            raise _UnattainedAmplitude("No finite inverse-amplitude optimum")
        p[name] = sign * inverse ** (-1.0 / power)

    def stage(self, q: Quantity, base: Mapping[str, float]) -> tuple[dict[str, float], float]:
        stage = next(s for s in self.mode.stages if s.quantity == q)
        amp = self.amplitude(q)
        names = [n for n in stage.parameters if n in self.free and n != amp]
        p = dict(base)
        self.profile(q, p)
        target = self.data[q][1] * _SCALE[q]
        if not names:
            return p, 0.0
        coordinates = _Coordinates(names, p, self.bound)
        x, lower, upper = coordinates.point, coordinates.lower, coordinates.upper

        profiling = True

        def evaluate(z: np.ndarray) -> np.ndarray:
            v = dict(base) | coordinates.decode(z)
            if profiling:
                self.profile(q, v)
            return self.predict(q, v) * _SCALE[q] - target

        # Invalid density trials are rejected; valid-domain numerical failures propagate.
        initial = evaluate(x)

        def residual(z: np.ndarray) -> np.ndarray:
            try:
                return evaluate(z)
            except mm.NoFiniteChemicalPotentialError:
                return np.full_like(target, np.inf)

        def jacobian(z: np.ndarray) -> np.ndarray:
            return _validated_jacobian(evaluate, z, lower, upper)

        # Independently audit scaled projected stationarity at the supplied vector.
        # An xtol/ftol exit or an unchanged candidate cannot certify convergence.
        # Keep the amplitude exactly as returned during this derivative audit.
        profiling = amp is not None and base[amp] == 0.0
        audit_residual = evaluate(x)
        start_jac = jacobian(x)
        profiling = True
        stationarity = _projected_optimality(start_jac, audit_residual, x, lower, upper)
        result = least_squares(
            residual,
            x,
            jac=jacobian,
            bounds=(lower, upper),
            ftol=1e-11,
            xtol=1e-11,
            gtol=1e-8,
            max_nfev=250,
        )
        # Flat initial derivatives can terminate immediately in a populated/hidden-band limit.
        # A stationary full-rank nonzero-residual optimum does not need recovery.
        # Rank loss can conceal a useful direction even when its computed gradient is zero.
        deficient = np.linalg.matrix_rank(start_jac) < len(names)
        nonstationary = stationarity > _STATIONARITY_TOL
        if (
            np.linalg.norm(result.x - x) <= 1e-10
            and np.dot(initial, initial) > 1e-8
            and (deficient or nonstationary)
        ):
            seeds = [coordinates.multiply(x, factor) for factor in (0.5, 2.0)]
            # Restore an order-one public mass as well as local scale probes; multiplying
            # a numerically hidden 1e-20 band by two cannot reveal its sensitivity.
            seed = x.copy()
            if "m_eff" in names:
                i = names.index("m_eff")
                seed[i] = np.clip(0.0, lower[i], upper[i])
                seeds.append(seed)
            for seed in seeds:
                if np.array_equal(seed, x):
                    continue
                try:
                    evaluate(seed)
                except mm.NoFiniteChemicalPotentialError:
                    continue
                self.recoveries += 1
                trial_result = least_squares(
                    residual,
                    seed,
                    jac=jacobian,
                    bounds=(lower, upper),
                    ftol=1e-11,
                    xtol=1e-11,
                    gtol=1e-8,
                    max_nfev=125,
                )
                if np.dot(trial_result.fun, trial_result.fun) < np.dot(result.fun, result.fun):
                    result = trial_result
        p.update(coordinates.decode(result.x))
        self.profile(q, p)
        return p, stationarity

    def result(self, status: FitStatus, termination: str, consistent: bool) -> FitResult:
        residuals = {}

        # Terminal diagnostics have a bounded number of independent kernel calls
        # outside the optimization budget, always at the exact retained endpoint.
        def final_prediction(q: Quantity, p: Mapping[str, float]) -> np.ndarray:
            self.evaluations += 1
            return _evaluate_quantity(
                q, self.data[q][0], p, self.mode.id, self.request.scattering, self.n
            )

        unidentified: set[str] = set()
        for q in self.mode.quantities:
            predicted = final_prediction(q, self.values)
            delta = predicted - self.data[q][1]
            magnitude = float(np.linalg.norm(self.data[q][1]))
            residuals[q] = ResidualDiagnostics(
                float(np.linalg.norm(delta) / np.sqrt(len(delta))),
                float(np.linalg.norm(delta) / magnitude) if magnitude else None,
                QUANTITY_UNITS[q],
            )
            self.objectives[q] = float(np.dot(delta * _SCALE[q], delta * _SCALE[q]))
            amp = self.amplitude(q)
            if amp in self.free:
                sign = np.sign(self.values[amp]) if amp == "band_mass" else 1.0
                shape = final_prediction(q, self.values | {amp: float(sign)})
                if np.linalg.norm(shape) == 0:
                    unidentified.add(amp)
            stage = next(s for s in self.mode.stages if s.quantity == q)
            names = [n for n in stage.parameters if n in self.free and n != amp]
            jac = np.empty((len(delta), 0))
            x = lower = upper = np.empty(0)
            if names:
                coordinates = _Coordinates(names, self.values, self.bound)
                x, lower, upper = coordinates.point, coordinates.lower, coordinates.upper

                def at_final(
                    z: np.ndarray,
                    q: Quantity = q,
                    coordinates: _Coordinates = coordinates,
                ) -> np.ndarray:
                    return final_prediction(q, self.values | coordinates.decode(z)) * _SCALE[q]

                jac = _validated_jacobian(at_final, x, lower, upper)
                unidentified.update(
                    n for n, column in zip(names, jac.T, strict=True) if np.linalg.norm(column) == 0
                )
            # Include the analytic reciprocal-amplitude direction in the same
            # terminal-vector gradient, even if the budget interrupted a sweep.
            if amp in self.free:
                assert amp is not None
                power = 1.5 if q == "hall" else 1.0
                inverse = abs(self.values[amp]) ** (-power)
                edges = sorted((abs(self.bound(amp).lower), abs(self.bound(amp).upper)))
                inv_low = edges[1] ** (-power) / inverse
                inv_high = edges[0] ** (-power) / inverse if edges[0] else np.inf
                jac = np.column_stack((jac, predicted * _SCALE[q]))
                x = np.append(x, 1.0)
                lower = np.append(lower, inv_low)
                upper = np.append(upper, inv_high)
            self.optimality[q] = (
                _projected_optimality(jac, delta * _SCALE[q], x, lower, upper)
                if jac.shape[1]
                else 0.0
            )
        issues = active_issue_ids(
            self.mode,
            self.request.scattering,
            self.values,
            self.n,
            extrapolated=self.request.extrapolated,
        )
        at_bounds = []
        for n in sorted(self.free):
            b = self.bound(n)
            v = self.values[n]
            if any(
                np.isfinite(edge) and abs(v - edge) <= 1e-6 * max(abs(edge), 1.0)
                for edge in (b.lower, b.upper)
            ):
                at_bounds.append(n)
        return FitResult(
            dict(self.values),
            status,
            self.iterations if self.mode.iterative else None,
            parameter_errors={},
            at_bounds=tuple(at_bounds),
            known_issues=tuple(i for i in issues if i != "dpb_loop_degeneracy"),
            held=tuple(sorted(self.request.held)),
            algorithm="verified-sequential-v2",
            diagnostics=FitDiagnostics(
                termination,
                consistent,
                dict(self.objectives),
                dict(self.optimality),
                self.evaluations,
                self.recoveries,
                residuals,
                tuple(sorted(unidentified)),
            ),
        )


def _failed(
    request: FitRequest,
    engine: _Engine | None,
    error: Exception,
    termination: str = "numerical_failure",
) -> FitResult:
    from seeband_core.band_models import _failure_message, _log_failure

    _log_failure(error)
    if isinstance(error, DerivativeValidationError):
        termination = "derivative_validation_failure"
    return FitResult(
        dict(request.start),
        "failed",
        message=(
            "The fit derivative could not be verified in the admissible domain."
            if isinstance(error, DerivativeValidationError)
            else _failure_message(error)
        ),
        held=tuple(sorted(request.held)),
        algorithm="verified-sequential-v2",
        diagnostics=FitDiagnostics(
            termination,
            False,
            {},
            {},
            engine.evaluations if engine else 0,
            engine.recoveries if engine else 0,
            {},
            (),
        ),
    )


def fit_verified(
    request: FitRequest, mode: FitMode, on_iteration: IterationCallback | None = None
) -> FitResult:
    """Fit each declared stage and audit every stage at the exact returned vector."""
    engine: _Engine | None = None
    callback_error: Exception | None = None
    try:
        engine = _Engine(request, mode)
        # Require a valid start before the optimizer may reject invalid trial points.
        for q in mode.quantities:
            p = dict(engine.values)
            engine.profile(q, p)
            engine.predict(q, p)
            # Establish a finite profiled endpoint before any nonlinear stage can
            # consume the shared budget, including a permitted free A=0 start.
            engine.values = p
        history: list[np.ndarray] = []
        for iteration in range(1, (mode.max_iterations or 1) + 1):
            for q in mode.quantities:
                engine.values, _ = engine.stage(q, engine.values)
            engine.iterations = iteration
            if mode.iterative and on_iteration is not None:
                try:
                    on_iteration(IterationUpdate(iteration, dict(engine.values)))
                except FitStopped:
                    return engine.result("stopped", "callback", False)
                except Exception as error:
                    callback_error = error
                    break
            final = dict(engine.values)
            consistent = True
            for q in mode.quantities:
                before = engine.predict(q, final) * _SCALE[q] - engine.data[q][1] * _SCALE[q]
                candidate, stationarity = engine.stage(q, final)
                after = engine.predict(q, candidate) * _SCALE[q] - engine.data[q][1] * _SCALE[q]
                old, new = float(np.dot(before, before)), float(np.dot(after, after))
                gain = max(0.0, old - new)
                engine.optimality[q] = stationarity
                if gain > _AUDIT_RTOL * max(1.0, old) or stationarity > _STATIONARITY_TOL:
                    consistent = False
            if consistent:
                return engine.result("converged", "conditional_stage_optima", True)
            vector = np.array([final[n] for n in sorted(engine.free)])
            if any(np.allclose(vector, v, rtol=1e-10, atol=1e-12) for v in history):
                return engine.result("stalled", "cycle_or_stall", False)
            history.append(vector)
        if callback_error is None:
            return engine.result("iteration_limit", "sweep_budget", False)
    except _BudgetReached:
        assert engine is not None
        try:
            return engine.result("iteration_limit", "evaluation_budget", False)
        except (ValueError, OverflowError, FloatingPointError) as error:
            return _failed(request, engine, error, "budget_before_valid_endpoint")
    except MemoryError:
        raise
    except Exception as error:
        return _failed(request, engine, error)
    assert callback_error is not None
    raise callback_error


def evaluate(
    model_id: str,
    fit_mode: str,
    parameters: Mapping[str, float],
    temperature_k: np.ndarray,
    scattering: str | None,
    degen: float = 1.0,
    *,
    quantities: tuple[Quantity, ...] | None = None,
    check_finite: bool = True,
) -> dict[Quantity, np.ndarray]:
    """Evaluate built-in measured quantities on the supplied temperatures in core units."""
    from seeband_core.model_descriptions import load_desktop_descriptions

    if model_id not in ("spb", "dpb") or not fit_mode.startswith(model_id + "_"):
        raise ValueError("Unknown built-in model")
    mode = load_desktop_descriptions()[model_id].fit_mode(fit_mode)
    mode.parameters_for(scattering)
    if not 0 < degen < np.inf:
        raise ValueError("Band degeneracies must be positive")
    selected = mode.quantities if quantities is None else quantities
    if any(q not in mode.quantities for q in selected):
        raise ValueError("Quantity is not available for this fit mode")
    return {
        q: _evaluate_quantity(
            q, temperature_k, parameters, fit_mode, scattering, degen, check_finite
        )
        for q in selected
    }
