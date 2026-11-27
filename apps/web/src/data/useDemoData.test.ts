// @vitest-environment node
import { describe, expect, test } from "vitest";

import { DEMO as EXAMPLE } from "../../e2e/support/models";

import type { DemoResponse } from "@/api/client";
import { demoEntries, demoText } from "@/data/useDemoData";
import type { Measurement } from "@/session/store";

const DEMO = EXAMPLE as unknown as DemoResponse;

describe("demoText", () => {
  test("holds each row, with numbers that read back exactly", () => {
    const measurement = {
      temperature_k: [50, 75.5],
      values: [1.2345678901234e-5, -3e-7],
    } as Measurement;

    const lines = demoText(measurement).split("\n");

    expect(lines).toHaveLength(2);
    const [temperature, value] = (lines[0] ?? "").split(" ");
    expect(Number(temperature)).toBe(50);
    expect(Number(value)).toBe(1.2345678901234e-5);
    expect(lines[1]).toBe("75.5 -3e-7");
  });
});

describe("demoEntries", () => {
  test("labels each quantity with the demo's own message", () => {
    const entries = demoEntries(DEMO);

    expect(entries.map(([quantity]) => quantity)).toEqual([
      "seebeck",
      "resistivity",
      "hall",
    ]);
    for (const [quantity, entry] of entries) {
      expect(entry.source).toEqual({
        kind: "demo",
        messageKey: DEMO.message_key,
      });
      expect(entry.measurement).toBe(DEMO.measurements[quantity]);
      expect(entry.extrapolated).toBe(false);
      expect(entry.text.split("\n")).toHaveLength(entry.measurement.points);
    }
  });

  test("leaves out what the demo does not hold", () => {
    const measurements = { ...DEMO.measurements };
    delete measurements.hall;
    expect(
      demoEntries({ ...DEMO, measurements }).map(([quantity]) => quantity),
    ).toEqual(["seebeck", "resistivity"]);
  });
});

describe("explicit synthetic demo initialization", () => {
  test("opens a Fermi-energy session with the synthetic reference filling and mass", async () => {
    const { applyDemo } = await import("./useDemoData");
    const { apiClient } = await import("@/api/client");
    const { useSessionStore } = await import("@/session/store");
    const { MODELS } = await import("../../e2e/support/models");
    const { vi } = await import("vitest");
    const original = useSessionStore.getState();
    const legacy =
      MODELS.models as import("@/model/selection").ModelDescription[];
    const models = legacy.map((model) =>
      model.id !== "dpb"
        ? model
        : {
            ...model,
            fit_modes: model.fit_modes.map((mode) => ({
              ...mode,
              parameters: mode.parameters.map((parameter) => ({
                ...parameter,
                name:
                  parameter.name === "m_eff"
                    ? "mass_ratio"
                    : parameter.name === "band_gap"
                      ? "band_offset_k"
                      : parameter.name,
              })),
            })),
          },
    );
    const registry = vi
      .spyOn(apiClient, "getModels")
      .mockResolvedValue({ models: legacy } as Awaited<
        ReturnType<typeof apiClient.getModels>
      >);
    const convert = vi.spyOn(apiClient, "migrateDpb").mockResolvedValue({
      parameterization: "explicit_density_v1",
      band_configuration: "vb_cb",
      net_electron_density_per_m3: -3e24,
      parameters: { m1: 1.4, mass_ratio: 1.2, band_offset_k: 800 },
    });
    try {
      useSessionStore.setState({
        selection: {
          ...original.selection,
          model: "dpb",
          parameterization: "explicit_density_v1",
          netElectronDensityPerM3: -2e24,
          legacySource: "Archived fit",
        },
      });
      await applyDemo(DEMO, models);
      const state = useSessionStore.getState();
      expect(convert).toHaveBeenCalledWith(
        expect.objectContaining({
          m1: 1.4,
          band_1_degeneracy: 1,
          band_2_degeneracy: 1,
        }),
        undefined,
      );
      expect(state.selection).toMatchObject({
        parameterization: "explicit_fermi_v1",
        bandConfiguration: "vb_cb",
      });
      expect(state.selection.netElectronDensityPerM3).toBeUndefined();
      expect(state.selection.carrierType).toBeUndefined();
      expect(state.selection.legacySource).toBeUndefined();
      expect(state.parameters[DEMO.fit_mode]).toEqual({
        m1: 1.4,
        fermi_energy: DEMO.true_parameters.fermi_energy,
      });
      expect(state.guessedParameters).toEqual({});
      expect(state.data.seebeck?.source.kind).toBe("demo");
      useSessionStore.setState(original, true);
      let deliver: (
        point: Awaited<ReturnType<typeof apiClient.migrateDpb>>,
      ) => void = () => undefined;
      convert.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            deliver = resolve;
          }),
      );
      const hydration = applyDemo(DEMO, models);
      await vi.waitFor(() => expect(convert).toHaveBeenCalledTimes(2));
      useSessionStore.getState().setParameter(DEMO.fit_mode, "mass_ratio", 2.3);
      deliver({
        parameterization: "explicit_density_v1",
        band_configuration: "vb_cb",
        net_electron_density_per_m3: -3e24,
        parameters: { m1: 1.4 },
      });
      await hydration;
      expect(
        useSessionStore.getState().parameters[DEMO.fit_mode]?.mass_ratio,
      ).toBe(2.3);
      expect(useSessionStore.getState().data).toEqual({});
      useSessionStore.setState(original, true);
      convert.mockRejectedValueOnce(new Error("Conversion unavailable"));
      await expect(applyDemo(DEMO, models)).rejects.toThrow(
        "Conversion unavailable",
      );
      expect(useSessionStore.getState().data).toEqual({});
    } finally {
      registry.mockRestore();
      convert.mockRestore();
      useSessionStore.setState(original, true);
    }
  });
});
