// The sitemap: every page of the site but the 404 page, at its address with a trailing slash, as
// the build writes each page as a directory. It needs absolute addresses, so a build for a closed
// host, without a site address, lists none.
import type { APIRoute } from "astro";

const PAGES = Object.keys(import.meta.glob("./**/*.{astro,md,mdx}"));

/** A page's address from its file: ./guide.mdx and ./guide/index.mdx are both /guide/. */
function pathOf(file: string): string {
  const path = file
    .replace(/^\.\//, "")
    .replace(/\.(astro|md|mdx)$/, "")
    .replace(/(^|\/)index$/, "");
  return path === "" ? "/" : `/${path}/`;
}

export const GET: APIRoute = ({ site }) => {
  const urls = (site === undefined ? [] : PAGES)
    .filter((file) => !file.endsWith("/404.astro"))
    .map(pathOf)
    .sort()
    .map((path) => `  <url><loc>${new URL(path, site).href}</loc></url>`);
  const xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...urls,
    "</urlset>",
  ].join("\n");
  return new Response(`${xml}\n`, {
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
};
