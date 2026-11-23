import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { loadPlotly } from "@/charts/loadPlotly";
import {
  TransportChart,
  type TransportChartProps,
} from "@/charts/TransportChart";

vi.mock("@/charts/loadPlotly", () => ({ loadPlotly: vi.fn() }));

const react = vi.fn(() => Promise.resolve());
const purge = vi.fn();
const load = vi.mocked(loadPlotly);

const PROPS: TransportChartProps = {
  curves: [{ id: "a", label: "Model", temperatureK: [100], values: [1] }],
  measurements: { label: "Data", temperatureK: [100], values: [1] },
  xAxisTitle: "T, K",
  yAxisTitle: "S",
  description: "Chart of S against temperature",
  failedText: "The chart could not load",
};

beforeEach(() => {
  react.mockClear();
  purge.mockClear();
  load.mockReset();
  load.mockResolvedValue({ react, purge } as never);
});

afterEach(cleanup);

test("an empty state shows instead, and Plotly does not load", () => {
  render(
    <TransportChart {...PROPS} empty={{ title: "No data", text: "Upload" }} />,
  );

  expect(screen.getByText("No data")).toBeTruthy();
  expect(screen.getByText("Upload")).toBeTruthy();
  expect(load).not.toHaveBeenCalled();
  expect(screen.queryByRole("img")).toBeNull();
});

test("a chart has its description for a screen reader, and draws once loaded", async () => {
  render(<TransportChart {...PROPS} />);

  const chart = screen.getByRole("img", { name: PROPS.description });
  await waitFor(() => {
    expect(react).toHaveBeenCalledTimes(1);
  });
  expect(react.mock.calls[0]?.at(0)).toBe(chart);
});

test("new data updates the same drawing, and the end clears it", async () => {
  const { rerender, unmount } = render(<TransportChart {...PROPS} />);
  await waitFor(() => {
    expect(react).toHaveBeenCalledTimes(1);
  });

  rerender(
    <TransportChart
      {...PROPS}
      curves={[{ id: "a", label: "Model", temperatureK: [100], values: [2] }]}
    />,
  );

  await waitFor(() => {
    expect(react).toHaveBeenCalledTimes(2);
  });
  expect(purge).not.toHaveBeenCalled();

  unmount();

  expect(purge).toHaveBeenCalledTimes(1);
});

test("the same props draw nothing again", async () => {
  const { rerender } = render(<TransportChart {...PROPS} />);
  await waitFor(() => {
    expect(react).toHaveBeenCalledTimes(1);
  });

  rerender(<TransportChart {...PROPS} />);
  await new Promise((resolve) => setTimeout(resolve, 20));

  expect(react).toHaveBeenCalledTimes(1);
});

test("there is no toggle of measurements, and a failed load says so", async () => {
  load.mockRejectedValue(new Error("offline"));

  render(<TransportChart {...PROPS} measurements={null} />);

  expect(screen.queryByRole("switch")).toBeNull();
  expect(await screen.findByText(PROPS.failedText)).toBeTruthy();
});

test.each([
  ["rejects", () => Promise.reject(new Error("SECRET-VALUE"))],
  [
    "throws",
    () => {
      throw new Error("SECRET-VALUE");
    },
  ],
])("if drawing %s, the message shows, with no details", async (_, draw) => {
  react.mockImplementationOnce(draw);

  render(<TransportChart {...PROPS} />);

  expect(await screen.findByText(PROPS.failedText)).toBeTruthy();
  expect(document.body.textContent).not.toContain("SECRET-VALUE");
});

test("with nothing to name, there is no empty legend", () => {
  render(<TransportChart {...PROPS} curves={[]} measurements={null} />);

  expect(screen.queryByRole("list")).toBeNull();
});

test("leaving before Plotly has loaded draws nothing", async () => {
  let finish: (module: never) => void = () => undefined;
  load.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve as never;
    }),
  );
  const { unmount } = render(<TransportChart {...PROPS} />);

  unmount();
  finish({ react, purge } as never);
  await new Promise((resolve) => setTimeout(resolve, 20));

  expect(react).not.toHaveBeenCalled();
});
