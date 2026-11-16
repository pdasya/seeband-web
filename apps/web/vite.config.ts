import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The app calls `/api` on its own origin, as the API's errors have no CORS headers. This chooses
// where that goes: the mock by default, or the API with `pnpm dev:api`.
const apiProxy = {
  "/api": process.env.SEEBAND_API_TARGET ?? "http://127.0.0.1:4010",
};

// Exported files name the app's version.
const { version } = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf8"),
) as { version: string };

/**
 * The commit the app is built from: `SEEBAND_COMMIT`, which CI sets, or git's, with -dirty for
 * uncommitted changes, or null if neither knows, rather than a made-up value.
 */
function commit(): string | null {
  const chosen = process.env.SEEBAND_COMMIT?.trim();
  if (chosen) {
    return chosen;
  }
  const git = (...args: string[]) =>
    execFileSync("git", args, { encoding: "utf8", timeout: 5000 }).trim();
  try {
    const head = git("rev-parse", "--short=12", "HEAD");
    const changes = git("status", "--porcelain", "--untracked-files=no");
    return changes === "" ? head : `${head}-dirty`;
  } catch {
    return null;
  }
}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(version),
    __APP_COMMIT__: JSON.stringify(commit()),
  },
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"] },
});
