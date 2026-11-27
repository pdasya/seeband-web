// @vitest-environment jsdom
import { afterEach, expect, test } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ExplicitDpbControls } from "./ExplicitDpbControls";
import { useSessionStore } from "@/session/store";

const original = useSessionStore.getState();
afterEach(() => {
  cleanup();
  useSessionStore.setState(original, true);
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

test("archived fixed-density sessions keep their inputs without editable carrier controls", () => {
  useSessionStore.setState({
    selection: {
      ...original.selection,
      model: "dpb",
      parameterization: "explicit_density_v1",
      bandConfiguration: "vb_cb",
      netElectronDensityPerM3: -2e24,
    },
  });
  render(<ExplicitDpbControls />);
  expect(screen.queryByRole("radio")).toBeNull();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByText(/n − p =/)).toBeNull();
  expect((screen.getByRole("combobox") as HTMLSelectElement).disabled).toBe(
    true,
  );
  expect(useSessionStore.getState().selection.netElectronDensityPerM3).toBe(
    -2e24,
  );
});

test("Fermi sessions have no carrier-sign picker and preserve gap E_F when bands change", () => {
  useSessionStore.setState({
    selection: {
      ...original.selection,
      model: "dpb",
      fitMode: "dpb_s_rho",
      parameterization: "explicit_fermi_v1",
      bandConfiguration: "vb_cb",
    },
    parameters: {
      dpb_s_rho: { fermi_energy: 140, band_offset_k: 300, mass_ratio: 1.7 },
    },
    customBounds: { dpb_s_rho: { fermi_energy: { lower: -200, upper: 400 } } },
    held: { dpb_s_rho: ["fermi_energy", "mass_ratio"] },
  });
  render(<ExplicitDpbControls />);
  expect(screen.queryByRole("radio")).toBeNull();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.getByText(/may lie inside the band gap/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText(/Band configuration/), {
    target: { value: "cb_cb" },
  });
  expect(useSessionStore.getState().parameters.dpb_s_rho?.fermi_energy).toBe(
    140,
  );
  expect(useSessionStore.getState().customBounds.dpb_s_rho).toEqual({
    fermi_energy: { lower: -200, upper: 400 },
  });
  expect(useSessionStore.getState().held.dpb_s_rho).toEqual([
    "fermi_energy",
    "mass_ratio",
  ]);
  expect(useSessionStore.getState().parameters.dpb_s_rho).toEqual({
    fermi_energy: 140,
    band_offset_k: 300,
    mass_ratio: 1.7,
  });
  fireEvent.change(screen.getByLabelText(/Band configuration/), {
    target: { value: "vb_vb" },
  });
  expect(useSessionStore.getState().customBounds.dpb_s_rho).toEqual({
    fermi_energy: { lower: -200, upper: 400 },
  });
  expect(useSessionStore.getState().held.dpb_s_rho).toEqual([
    "fermi_energy",
    "mass_ratio",
  ]);
  expect(useSessionStore.getState().parameters.dpb_s_rho?.fermi_energy).toBe(
    140,
  );
  expect(useSessionStore.getState().selection.carrierType).toBeUndefined();
});
