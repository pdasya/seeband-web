import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { App } from "@/App";
import { Slider } from "@/components/ui/slider";

// Radix's slider measures itself, and jsdom has no ResizeObserver.
vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
);

afterEach(cleanup);

describe("base components", () => {
  test("each kind reaches a user with its role", () => {
    render(<App />);

    expect(screen.getByRole("button", { name: "Run fit" })).toBeTruthy();
    expect(screen.getByRole("spinbutton", { name: "N₁" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Scattering" })).toBeTruthy();
    expect(screen.getByRole("switch", { name: "Interpolation" })).toBeTruthy();
    expect(screen.getByRole("slider", { name: "m_eff" })).toBeTruthy();
    expect(screen.getAllByRole("tab")).toHaveLength(3);
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getAllByRole("alert")).toHaveLength(2);
    expect(screen.getByText("Converged in 7 iter.")).toBeTruthy();
  });

  test("a slider with no value has one thumb, with a value and the name", () => {
    render(<Slider aria-label="Only" />);

    const thumbs = screen.getAllByRole("slider");
    expect(thumbs).toHaveLength(1);
    expect(thumbs[0]?.getAttribute("aria-valuenow")).toBe("0");
    expect(thumbs[0]?.getAttribute("aria-label")).toBe("Only");
  });

  test("a slider has a thumb for each value", () => {
    render(<Slider aria-label="Range" defaultValue={[20, 60]} />);

    expect(screen.getAllByRole("slider", { name: "Range" })).toHaveLength(2);
  });
});
