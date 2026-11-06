import { getViteConfig } from "astro/config";

// Astro's Vite setup, so that a test can render `.astro` files.
export default getViteConfig({
  test: { include: ["tests/**/*.test.{ts,tsx}"] },
});
