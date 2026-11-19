// robots.txt. A public build keeps search engines out of the app and the API and names the
// sitemap; a build for a closed host, without a site address, keeps them out of everything.
import type { APIRoute } from "astro";

import { NOT_FOR_SEARCH } from "../strings";

export const GET: APIRoute = ({ site }) => {
  const lines =
    site === undefined
      ? ["User-agent: *", "Disallow: /"]
      : [
          "User-agent: *",
          ...NOT_FOR_SEARCH.map((path) => `Disallow: ${path}`),
          "",
          `Sitemap: ${new URL("/sitemap.xml", site).href}`,
        ];
  return new Response(`${lines.join("\n")}\n`, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
