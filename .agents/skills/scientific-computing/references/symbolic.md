# Symbolic checks and SymPy

Keep integers and rationals exact until approximation is intentional: use `Rational(1, 10)` rather than a binary float when one tenth is the mathematical input. Declare reality, positivity and domain assumptions before simplifying. Record logarithm/root branches and preserve excluded poles after cancellation. Scalar symbols do not represent noncommuting operators.

For example, `(x**2 - 1)/(x - 1)` simplifies to `x + 1` only with the original exclusion `x != 1`. The simplified expression has a value at that point; the original expression does not. A numerically evaluated removable limit and an allowed model input are different claims.

Verify transformations by substitution into the original expression, exact residuals where possible, and admissible numerical samples when useful. Check limits from relevant sides. A conditional or unresolved symbolic solution is not a complete solution set or proof of no solution; floating agreement at samples is not an identity proof.

Use SymPy for a specific uncertainty, such as a derivative or algebraic cancellation, and keep its assumptions with the result. Inspect generated expressions before translation. `lambdify` generates/evaluates code: use only trusted expressions, symbols and mappings, never untrusted user strings. Specify the intended numeric backend and check behavior near domain boundaries after translation.

For installed-version details consult official [SymPy assumptions](https://docs.sympy.org/latest/guides/assumptions.html) and [lambdify documentation](https://docs.sympy.org/latest/modules/utilities/lambdify.html). Symbolic output still needs the physical conventions and validity checks of the approved model.
