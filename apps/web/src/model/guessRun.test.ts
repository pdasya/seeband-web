// @vitest-environment node
import { beforeEach, describe, expect, test } from "vitest";

import { MODELS } from "../../e2e/support/models";

import { guessModel, isNewLoad } from "@/model/guessRun";
import type { ModelDescription } from "@/model/selection";
import type { Measurement } from "@/session/store";

const models = MODELS.models as ModelDescription[];

const rows = (...values: number[]) =>
  ({
    temperature_k: values.map((_, index) => 100 + index),
    values,
  }) as unknown as Measurement;

describe("guessModel", () => {
  test("is the one the API says has nets", () => {
    expect(guessModel(models)?.id).toBe("dpb");
    expect(
      guessModel(models.filter(({ has_initial_guess: has }) => !has)),
    ).toBeUndefined();
    expect(guessModel(undefined)).toBeUndefined();
  });
});

describe("isNewLoad", () => {
  beforeEach(() => {
    isNewLoad(undefined);
  });

  test("a new file is one, and no data are not", () => {
    expect(isNewLoad(undefined)).toBe(false);
    expect(isNewLoad(rows(1))).toBe(true);
  });

  test("the same data coming back are not, after another file or none", () => {
    const first = rows(1);
    expect(isNewLoad(first)).toBe(true);
    expect(isNewLoad(undefined)).toBe(false);
    expect(isNewLoad(first)).toBe(false);
    expect(isNewLoad(rows(2))).toBe(true);
    expect(isNewLoad(first)).toBe(false);
  });

  test("the same S read again in place is not, as from a new mapping", () => {
    expect(isNewLoad(rows(1, 2))).toBe(true);
    expect(isNewLoad(rows(1, 2))).toBe(false);
    expect(isNewLoad(rows(1, 3))).toBe(true);
  });

  test("the same file loaded after removing the last is", () => {
    expect(isNewLoad(rows(1))).toBe(true);
    expect(isNewLoad(undefined)).toBe(false);
    expect(isNewLoad(rows(1))).toBe(true);
  });
});
