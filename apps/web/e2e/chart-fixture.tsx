import { useState } from "react";
import { createRoot } from "react-dom/client";

import { TransportChart } from "@/charts/TransportChart";
import "@/index.css";

// Fixed data, with a gap in the first curve, for the browser tests. It is not in a production build.
const TEMPERATURE_K = [50, 100, 200, 300, 400, 500, 600, 700, 800];
const MODEL = [10, 40, 90, null, 120, 110, 95, 80, 70];
const MEASURED = [12, 38, 92, 118, 121, 109, 96, 78, 71];

function Fixture() {
  const [shift, setShift] = useState(0);
  const empty = new URLSearchParams(window.location.search).has("empty");
  return (
    <main style={{ width: 1000, padding: 24 }}>
      <button type="button" onClick={() => setShift((value) => value + 50)}>
        Move
      </button>
      <TransportChart
        empty={empty ? { title: "No data yet", text: "Upload a file" } : null}
        curves={[
          {
            id: "model",
            label: "Model",
            temperatureK: TEMPERATURE_K,
            values: MODEL.map((value) =>
              value === null ? null : value + shift,
            ),
          },
          {
            id: "band",
            label: "Band 2",
            temperatureK: TEMPERATURE_K,
            values: MODEL.map((value) => (value ?? 50) / 2),
            dashed: true,
          },
        ]}
        measurements={{
          label: "Measurements",
          temperatureK: TEMPERATURE_K,
          values: MEASURED,
        }}
        fitRange={{ minK: 100, maxK: 700 }}
        referenceLines={[{ value: 60, label: "Band edge" }]}
        xAxisTitle="T, K"
        yAxisTitle="S, µV/K"
        description="Chart of S against temperature"
        toggleMeasurementsLabel="Show measurements"
        failedText="The chart could not load"
      />
    </main>
  );
}

const root = document.getElementById("root");
if (root !== null) {
  createRoot(root).render(<Fixture />);
}
