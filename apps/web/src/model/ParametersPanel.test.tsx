import assert from "node:assert/strict";
// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import contract from "../../../../packages/api-client/openapi.json";
import { ParametersPanel } from "@/model/ParametersPanel";
import type { ModelDescription } from "@/model/selection";
import { useSessionStore } from "@/session/store";

vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
);
const MODELS = Object.values(
  contract.paths["/api/models"].get.responses["200"].content["application/json"]
    .examples,
)[0]?.value;
assert(MODELS);
const original = useSessionStore.getState();
afterEach(() => {
  cleanup();
  useSessionStore.setState(original, true);
});

test("ionized S-only structural B stays editable and has no hold control", () => {
  const source = (MODELS.models as ModelDescription[]).find(
    (model) => model.id === "dpb",
  );
  assert(source);
  const mode = source.fit_modes.find((mode) => mode.id === "dpb_s");
  assert(mode);
  const rho = source.fit_modes.find((mode) => mode.id === "dpb_s_rho");
  assert(rho);
  const b = rho.parameters.find((p) => p.name === "B");
  assert(b);
  const structural = {
    ...b,
    role: "fixed" as const,
    scattering: ["ionized"],
    bounds_editable: false,
    fit_bounds: null,
    display_range: { minimum: 0, maximum: 10000, step: 0.01, default: 1 },
  };
  const query = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity } },
  });
  // The panel reads the description of the session's parameterization.
  query.setQueryData(["models", "explicit_density_v1"], {
    ...MODELS,
    models: [
      {
        ...source,
        fit_modes: [
          { ...mode, parameter_overrides: { ionized: [structural] } },
        ],
      },
    ],
  });
  useSessionStore.setState({
    selection: {
      ...original.selection,
      model: "dpb",
      fitMode: "dpb_s",
      scattering: "ionized",
      parameterization: "explicit_density_v1",
    },
    parameters: { dpb_s: { B: 1 } },
    customBounds: { dpb_s: { B: { lower: 0.9, upper: 1.1 } } },
  });
  render(
    <QueryClientProvider client={query}>
      <ParametersPanel />
    </QueryClientProvider>,
  );
  const field = screen.getByRole("textbox", { name: "B" }) as HTMLInputElement;
  expect(field.disabled).toBe(false);
  expect(screen.queryByRole("button", { name: /Hold B/ })).toBeNull();
  fireEvent.change(field, { target: { value: "9" } });
  fireEvent.blur(field);
  expect(useSessionStore.getState().parameters.dpb_s?.B).toBe(9);
});
