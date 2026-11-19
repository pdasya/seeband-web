import mdx from "@astrojs/mdx";
import { defineConfig } from "astro/config";

import { markdown } from "./markdown.mjs";

// Static HTML for Caddy, at `/`, where the app's header links. English only for now.
// SEEBAND_SITE_URL is the public address, such as https://seeband.example. Without it the build is
// for a host closed to search engines: every page says noindex, robots.txt disallows everything,
// and there is no sitemap, canonical address or og:url, as they need an absolute address.
const site = siteAddress(process.env.SEEBAND_SITE_URL);

/**
 * The site's address: an http or https origin, as the site is served at the root of its host. A
 * path would be dropped from every address the build writes, so it is refused, as is anything
 * that is not an address.
 */
function siteAddress(value) {
  if (value === undefined || value === "") return undefined;
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error(
      `SEEBAND_SITE_URL must be an address such as https://seeband.example, not "${value}"`,
    );
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.pathname !== "/" ||
    url.search !== "" ||
    url.hash !== "" ||
    url.username !== "" ||
    url.password !== ""
  ) {
    throw new Error(
      `SEEBAND_SITE_URL must be an http or https origin with no path, such as https://seeband.example, not "${value}"`,
    );
  }
  return url.origin;
}

export default defineConfig({
  site,
  output: "static",
  trailingSlash: "ignore",
  build: { format: "directory" },
  integrations: [mdx()],
  markdown,
});
