import { defineConfig } from "@playwright/test";

const PORT = 4190;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: process.env.CI !== undefined,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${String(PORT)}`,
    viewport: { width: 1440, height: 900 },
    // CI installs Playwright's Chromium, and a developer has Chrome.
    ...(process.env.CI === undefined ? { channel: "chrome" } : {}),
  },
  webServer: {
    command: `node_modules/.bin/vite --port ${String(PORT)} --strictPort`,
    url: `http://localhost:${String(PORT)}/e2e/chart-fixture.html`,
    reuseExistingServer: false,
  },
});
