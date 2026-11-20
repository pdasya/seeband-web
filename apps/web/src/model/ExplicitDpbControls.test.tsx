// @vitest-environment jsdom
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ExplicitDpbControls } from "./ExplicitDpbControls";
import { useSessionStore } from "@/session/store";

vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
);

const original = useSessionStore.getState();
afterEach(() => {
  cleanup();
  useSessionStore.setState(original, true);
});

function open(
  density = 2e24,
  configuration: "vb_vb" | "vb_cb" | "cb_cb" = "vb_cb",
) {
  useSessionStore.setState({
    selection: {
      ...original.selection,
      model: "dpb",
      parameterization: "explicit_density_v1",
      bandConfiguration: configuration,
      netElectronDensityPerM3: density,
    },
  });
  return render(<ExplicitDpbControls />);
}
const magnitude = () =>
  screen.getByRole("textbox", {
    name: "Carrier excess magnitude |n − p| (m⁻³)",
  });

test("historical provenance is safe text even for a malformed imported string", () => {
  useSessionStore.setState({
    selection: {
      ...original.selection,
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

test("mixed bands switch p/n while preserving the nonnegative magnitude", () => {
  open();
  fireEvent.click(screen.getByRole("radio", { name: "p: excess holes" }));
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(
    -2e24,
  );
  expect(magnitude().getAttribute("value")).toBe("2e+24");
  expect(screen.getByText("n − p = −2e+24 m⁻³ (p)")).toBeTruthy();
  fireEvent.click(screen.getByRole("radio", { name: "n: excess electrons" }));
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(
    2e24,
  );
});

test("choosing p at intrinsic zero controls the next magnitude without inventing density", () => {
  open(0);
  fireEvent.click(screen.getByRole("radio", { name: "p: excess holes" }));
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(0);
  expect(screen.getByText(/Intrinsic: n = p/)).toBeTruthy();
  fireEvent.change(magnitude(), { target: { value: "3e24" } });
  fireEvent.blur(magnitude());
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(
    -3e24,
  );
});

test("same-type branches select the compatible sign explicitly and preserve magnitude", () => {
  open();
  fireEvent.change(screen.getByLabelText(/Band configuration/), {
    target: { value: "vb_vb" },
  });
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(
    -2e24,
  );
  expect(
    screen
      .getByRole("radio", { name: "n: excess electrons" })
      .hasAttribute("disabled"),
  ).toBe(true);
  expect(screen.getByText(/VB \+ VB requires p/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText(/Band configuration/), {
    target: { value: "cb_cb" },
  });
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(
    2e24,
  );
  expect(
    screen
      .getByRole("radio", { name: "p: excess holes" })
      .hasAttribute("disabled"),
  ).toBe(true);
});

test("same-type zero requires a positive magnitude and never substitutes a density", () => {
  open(0);
  fireEvent.change(screen.getByLabelText(/Band configuration/), {
    target: { value: "cb_cb" },
  });
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(0);
  expect(screen.getByRole("alert").textContent).toContain("positive");
  fireEvent.change(magnitude(), { target: { value: "-2e24" } });
  fireEvent.blur(magnitude());
  expect(magnitude().getAttribute("aria-invalid")).toBe("true");
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(0);
});

test("nearby tooltip opens by click and explains fixed excess, varying populations, units and sign constraints", () => {
  open();
  fireEvent.click(screen.getByRole("button", { name: "About carrier excess" }));
  const tooltip = screen.getByRole("tooltip");
  expect(tooltip.textContent).toContain("remain fixed");
  expect(tooltip.textContent).toContain("vary with temperature");
  expect(tooltip.textContent).toContain("per cubic metre");
  expect(tooltip.textContent).toContain("VB + VB");
  expect(tooltip.textContent).toContain("CB + CB");
});

test("blurring an unchanged magnitude preserves a completed fit", () => {
  open();
  const result = {
    status: "converged" as const,
    parameters: {},
    parameter_errors: {},
    at_bounds: [],
    known_issues: [],
    held: [],
    parameter_status: {},
  };
  useSessionStore.setState({ fit: { status: "done", result } });
  fireEvent.blur(magnitude());
  expect(useSessionStore.getState().fit).toEqual({ status: "done", result });
});

test("Fermi sessions select p/n without concentration or sign captions and preserve E_F", () => {
  useSessionStore.setState({
    selection: {
      ...original.selection,
      model: "dpb",
      fitMode: "dpb_s_rho",
      parameterization: "explicit_fermi_v1",
      bandConfiguration: "vb_cb",
      carrierType: "n",
    },
    parameters: { dpb_s_rho: { fermi_energy: 140 } },
  });
  render(<ExplicitDpbControls />);
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByText(/n − p =/)).toBeNull();
  fireEvent.click(screen.getByRole("radio", { name: "p: holes" }));
  expect(useSessionStore.getState().selection.carrierType).toBe("p");
  expect(useSessionStore.getState().parameters.dpb_s_rho?.fermi_energy).toBe(
    140,
  );
  fireEvent.change(screen.getByLabelText(/Band configuration/), {
    target: { value: "cb_cb" },
  });
  expect(useSessionStore.getState().selection.carrierType).toBe("n");
  expect(
    screen.getByRole("radio", { name: "p: holes" }).hasAttribute("disabled"),
  ).toBe(true);
  expect(useSessionStore.getState().parameters.dpb_s_rho?.fermi_energy).toBe(
    140,
  );
  expect(screen.getByText(/Adjust E_F in Parameters/)).toBeTruthy();
});

test("virgin configuration switches retain automatic E_F as a derived default", () => {
  useSessionStore.setState({
    selection: {
      ...original.selection,
      model: "dpb",
      fitMode: "dpb_s_rho",
      parameterization: "explicit_fermi_v1",
      bandConfiguration: "vb_cb",
      carrierType: "p",
    },
    parameters: {},
  });
  render(<ExplicitDpbControls />);
  fireEvent.change(screen.getByLabelText(/Band configuration/), {
    target: { value: "cb_cb" },
  });
  expect(
    useSessionStore.getState().parameters.dpb_s_rho?.fermi_energy,
  ).toBeUndefined();
  expect(useSessionStore.getState().selection.carrierType).toBe("n");
});
