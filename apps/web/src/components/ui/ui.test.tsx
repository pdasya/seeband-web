import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

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

describe("slider", () => {
  test("with no value, it has one thumb, with a value and the name", () => {
    render(<Slider aria-label="Only" />);

    const thumbs = screen.getAllByRole("slider");
    expect(thumbs).toHaveLength(1);
    expect(thumbs[0]?.getAttribute("aria-valuenow")).toBe("0");
    expect(thumbs[0]?.getAttribute("aria-label")).toBe("Only");
  });

  test("it has a thumb for each value", () => {
    render(<Slider aria-label="Range" defaultValue={[20, 60]} />);

    expect(screen.getAllByRole("slider", { name: "Range" })).toHaveLength(2);
  });
});
