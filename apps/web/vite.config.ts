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

export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(version) },
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"] },
});
