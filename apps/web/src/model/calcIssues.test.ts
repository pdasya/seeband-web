import { expect, test } from "vitest";

import { issueTemperatures } from "@/model/calcIssues";

test("affected temperatures are rounded, separated by semicolons and carry their unit", () => {
  expect(issueTemperatures([166.66666666666669, 133.33333333333334])).toBe(
    "133,3; 166,7 K",
  );
  expect(issueTemperatures([200, 200, 500])).toBe("200; 500 K");
});

test("many affected temperatures give a range with the unit inside", () => {
  const many = Array.from(
    { length: 20 },
    (_, i) => 100 + i * 21.05263157894737,
  );
  expect(issueTemperatures(many)).toBe("100–500 K (20 affected temperatures)");
});
