import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The app calls `/api` on its own origin, as the API's errors have no CORS headers. This chooses
// where that goes: the mock by default, or the API with `pnpm dev:api`.
const apiProxy = {
  "/api": process.env.SEEBAND_API_TARGET ?? "http://127.0.0.1:4010",
};

/**
 * The public site's paths, which Caddy serves beside the app on one origin. With
 * `SEEBAND_SITE_TARGET`, the dev server sends them to the built site there (`astro preview`), so
 * that links between the two work on one port. Not to `astro dev`: its modules use Vite's own
 * /@fs and /@id paths, which are this server's too. Without it, as in tests, they stay the app's.
 */
const siteTarget = process.env.SEEBAND_SITE_TARGET;
const siteProxy =
  siteTarget === undefined || siteTarget === ""
    ? {}
    : Object.fromEntries(
        [
          "^/$",
          "^/conventions(/|$)",
          "^/results-changed(/|$)",
          "^/guide(/|$)",
          "^/examples(/|$)",
          "^/_astro/",
          "^/favicon\\.svg$",
        ].map((path) => [path, siteTarget]),
      );

// Exported files name the app's version.
const { version } = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf8"),
) as { version: string };

// The checkout the app is built in, whose commit it names, and git's short form of a commit.
const checkout = fileURLToPath(new URL("../..", import.meta.url));
const SHORT = 12;

/**
 * The commit the app is built from: `SEEBAND_COMMIT`, which an image build should set, or git's,
 * with -dirty for uncommitted changes, or null if neither knows, rather than a made-up value. Git
 * is asked only if this project's checkout is its top level, as an app built inside some other
 * repository would otherwise name that one's commit. Read when the config loads, so the dev
 * server's -dirty is that of its start.
 */
function commit(): string | null {
  const chosen = process.env.SEEBAND_COMMIT?.trim();
  if (chosen) {
    // A full hash in git's short form, as a commit found in git reads.
    return /^[0-9a-f]{13,40}$/.test(chosen) ? chosen.slice(0, SHORT) : chosen;
  }
  const git = (...args: string[]) =>
    execFileSync("git", args, {
      cwd: checkout,
      encoding: "utf8",
      timeout: 2000,
      // A build with no git, or no checkout, says nothing about it, as null is the answer.
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  try {
    if (resolve(git("rev-parse", "--show-toplevel")) !== resolve(checkout)) {
      return null;
    }
    const head = git("rev-parse", `--short=${String(SHORT)}`, "HEAD");
    const changes = git("status", "--porcelain", "--untracked-files=no");
    return head === "" ? null : changes === "" ? head : `${head}-dirty`;
  } catch {
    return null;
  }
}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(version),
    __APP_COMMIT__: JSON.stringify(commit()),
  },
  server: { proxy: { ...apiProxy, ...siteProxy } },
  preview: { proxy: apiProxy },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"] },
});
