import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { App } from "@/App";
import { Button } from "@/components/ui/button";

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

  test("a button has the height and radius of the design", () => {
    render(<Button>Run</Button>);

    const { className } = screen.getByRole("button", { name: "Run" });
    expect(className).toContain("h-9");
    expect(className).toContain("rounded-md");
    expect(className).toContain("bg-primary");
  });
});
