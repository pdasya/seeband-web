// @vitest-environment node
import { describe, expect, test } from "vitest";

import { guessBadge, guessMessages } from "@/model/guessStatus";
import type { GuessOutcome } from "@/session/store";

const RANGE = { min_temperature_k: 25.5, max_temperature_k: 750 };
const APPLIED: GuessOutcome = {
  kind: "applied",
  netRange: RANGE,
  warnings: [],
};

describe("guessBadge", () => {
  test("gives the net's real range, while no fit has taken over", () => {
    expect(guessBadge(APPLIED, { status: "idle" })).toEqual({
      status: "suggested",
      detail: "· net 25,5–750 K",
    });
    expect(guessBadge(APPLIED, { status: "waiting" })).toBeNull();
    expect(guessBadge(null, { status: "idle" })).toBeNull();
    expect(
      guessBadge({ kind: "not_finite", warnings: [] }, { status: "idle" }),
    ).toBeNull();
  });
});

describe("guessMessages", () => {
  test("an applied guess says nothing unless it has a warning", () => {
    expect(guessMessages(APPLIED)).toEqual([]);
    expect(
      guessMessages({ ...APPLIED, warnings: ["underdetermined_fit"] })[0],
    ).toContain("too few temperatures");
    expect(
      guessMessages({ ...APPLIED, warnings: ["unsorted_temperature"] })[0],
    ).toContain("do not rise");
    // This one has its own outcome, so no text repeats it.
    expect(
      guessMessages({ ...APPLIED, warnings: ["m_eff_rounds_to_zero"] }),
    ).toEqual([]);
  });

  test("no net names its span and every range, with a comma", () => {
    expect(
      guessMessages({
        kind: "no_net",
        firstK: 100.25,
        lastK: 200,
        available: [RANGE, { min_temperature_k: 300, max_temperature_k: 800 }],
        warnings: [],
      })[0],
    ).toBe(
      "No neural net covers 100,3–200 K, so the values stay as they are. The nets cover 25,5–750 K, 300–800 K.",
    );
  });

  test("a limit has its own text", () => {
    expect(
      guessMessages({ kind: "failed", code: "rate_limited", warnings: [] })[0],
    ).toContain("Try again");
    expect(
      guessMessages({ kind: "failed", code: "other", warnings: [] })[0],
    ).toContain("could not be calculated");
  });
});
