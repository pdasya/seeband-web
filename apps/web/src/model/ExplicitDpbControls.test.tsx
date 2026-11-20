// @vitest-environment jsdom
import { afterEach, expect, test } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ExplicitDpbControls } from "./ExplicitDpbControls";
import { useSessionStore } from "@/session/store";

const original = useSessionStore.getState().selection;
afterEach(() => {
  cleanup();
  useSessionStore.setState({ selection: original });
});

test("historical provenance is safe text even for a malformed imported string", () => {
  useSessionStore.setState({
    selection: {
      ...original,
      model: "dpb",
      parameterization: "explicit_density_v1",
      bandConfiguration: "cb_cb",
      netElectronDensityPerM3: 2e24,
      legacySource: "{ malformed imported provenance",
    },
  });
  const { container } = render(<ExplicitDpbControls />);
  expect(container.querySelector("pre")?.textContent).toBe(
    "{ malformed imported provenance",
  );
});

test("changing branch preserves researcher-entered signed density and exposes an incompatible sign", () => {
  useSessionStore.setState({
    selection: {
      ...original,
      model: "dpb",
      parameterization: "explicit_density_v1",
      bandConfiguration: "cb_cb",
      netElectronDensityPerM3: 2e24,
    },
  });
  render(<ExplicitDpbControls />);
  fireEvent.change(screen.getByLabelText(/Band configuration/), {
    target: { value: "vb_vb" },
  });
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(
    2e24,
  );
  expect(screen.getByRole("alert").textContent).toContain("sign required");
});

test("blurring an unchanged density preserves a completed fit", () => {
  const result = {
    status: "converged" as const,
    parameters: {},
    parameter_errors: {},
    at_bounds: [],
    known_issues: [],
    held: [],
    parameter_status: {},
  };
  useSessionStore.setState({
    selection: {
      ...original,
      model: "dpb",
      parameterization: "explicit_density_v1",
      bandConfiguration: "vb_cb",
      netElectronDensityPerM3: 2e24,
    },
    fit: { status: "done", result },
  });
  render(<ExplicitDpbControls />);
  fireEvent.blur(
    screen.getByRole("textbox", { name: "Net electron density n − p (m⁻³)" }),
  );
  expect(useSessionStore.getState().fit).toEqual({ status: "done", result });
});
