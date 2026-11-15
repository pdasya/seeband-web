import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { FitAlgorithmControl, NumericalDiagnostics } from "@/model/FitControls";
import { useSessionStore, type FitState } from "@/session/store";

afterEach(cleanup);

test("diagnostics keep numerical consistency, zero-signal residuals and unknown quality distinct", () => {
  const fit: FitState = {
    status: "done",
    result: {
      parameters: {},
      parameter_errors: {},
      at_bounds: [],
      known_issues: [],
      held: [],
      status: "stalled",
      algorithm: "verified-sequential-v2",
      diagnostics: {
        termination: "cycle",
        stage_consistent: false,
        evaluations: 12,
        recoveries: 1,
        objectives: { seebeck: 1 },
        optimality: { seebeck: 0.1 },
        residuals: { seebeck: { rmse: 0.5, relative_l2: null, unit: "V/K" } },
        unidentified: ["m_eff"],
        uncertainty: "not_assessed",
        residual_adequacy: "not_assessed",
      },
    },
  };
  render(<NumericalDiagnostics fit={fit} />);
  expect(
    screen.getByText("Stages are not consistent at the returned parameters"),
  ).toBeTruthy();
  expect(
    screen.getByText(
      /RMSE 0,5 V\/K; relative L2 not defined for a zero signal/,
    ),
  ).toBeTruthy();
  expect(screen.getByText(/Fit-input residuals/)).toBeTruthy();
  expect(screen.getByText(/Not identified:/)).toBeTruthy();
  expect(
    screen.getByText(
      "Physical adequacy and parameter uncertainty have not been assessed.",
    ),
  ).toBeTruthy();
});

test("ionized scattering cannot select the legacy estimator", () => {
  useSessionStore.setState({
    selection: {
      ...useSessionStore.getState().selection,
      scattering: "ionized",
      algorithm: "verified-sequential-v2",
    },
  });
  render(<FitAlgorithmControl />);
  const legacy = screen.getByRole("option", {
    name: "Legacy sequential (reproduce earlier results)",
  }) as HTMLOptionElement;
  expect(legacy.disabled).toBe(true);
});
