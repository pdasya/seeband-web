import mdx from "@astrojs/mdx";
import { defineConfig } from "astro/config";

import { markdown } from "./markdown.mjs";

// Static HTML for Caddy, at `/`, where the app's header links. English only for now.
export default defineConfig({
  output: "static",
  trailingSlash: "ignore",
  build: { format: "directory" },
  integrations: [mdx()],
  markdown,
});
