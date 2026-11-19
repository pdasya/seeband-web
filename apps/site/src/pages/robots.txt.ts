// robots.txt. A public build keeps search engines out of the app and the API and names the
// sitemap; a build for a closed host, without a site address, keeps them out of everything. `$`
// ends a rule at the end of the path, as Google and Bing read it.
import type { APIRoute } from "astro";

import { APP_SCREENS, NOT_FOR_SEARCH_PREFIXES } from "../strings";

export const GET: APIRoute = ({ site }) => {
  const lines =
    site === undefined
      ? ["User-agent: *", "Disallow: /"]
      : [
          "User-agent: *",
          ...APP_SCREENS.flatMap((path) => [
            `Disallow: ${path}$`,
            `Disallow: ${path}?`,
            `Disallow: ${path}/`,
          ]),
          ...NOT_FOR_SEARCH_PREFIXES.map((path) => `Disallow: ${path}`),
          "",
          `Sitemap: ${new URL("/sitemap.xml", site).href}`,
        ];
  return new Response(`${lines.join("\n")}\n`, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
