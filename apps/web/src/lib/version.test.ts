// @vitest-environment node
import { expect, test } from "vitest";

import { APP_VERSION, withCommit } from "@/lib/version";

test("a version names its commit, and only a known one", () => {
  expect(withCommit("1.2.0", "abc123def456")).toBe(
    "1.2.0 (commit abc123def456)",
  );
  expect(withCommit("1.2.0", null)).toBe("1.2.0");
  expect(withCommit("1.2.0", undefined)).toBe("1.2.0");
});

test("the app's own version carries the commit its build found, if any", () => {
  expect(APP_VERSION).toBe(withCommit(__APP_VERSION__, __APP_COMMIT__));
  // Git's short form, or a value CI set, never a placeholder.
  if (__APP_COMMIT__ !== null) {
    expect(__APP_COMMIT__).not.toBe("");
  }
});
