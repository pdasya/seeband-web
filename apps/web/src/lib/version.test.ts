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

test("the app's own version carries the commit it was built from", () => {
  // Tests run in the repository, where git knows the commit.
  expect(APP_VERSION).toMatch(/^\S+ \(commit [0-9a-f]{12}(-dirty)?\)$/);
});
