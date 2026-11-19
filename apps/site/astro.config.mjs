import mdx from "@astrojs/mdx";
import { defineConfig } from "astro/config";

import { markdown } from "./markdown.mjs";

// Static HTML for Caddy, at `/`, where the app's header links. English only for now.
// SEEBAND_SITE_URL is the public address, such as https://seeband.example. Without it the build is
// for a host closed to search engines: every page says noindex, robots.txt disallows everything,
// and there is no sitemap, canonical address or og:url, as they need an absolute address.
const site = process.env.SEEBAND_SITE_URL || undefined;

export default defineConfig({
  site,
  output: "static",
  trailingSlash: "ignore",
  build: { format: "directory" },
  integrations: [mdx()],
  markdown,
});
