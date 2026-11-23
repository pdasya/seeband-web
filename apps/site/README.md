# apps/site

The public pages, built with Astro as static HTML for Caddy to serve at `/`. The app is a separate build on the same origin at `/fit` and `/results`, with its files under `/assets/`; the site's are under `/_astro/`, so the two do not collide. Links between them are plain links.

```sh
pnpm --filter @seeband/site dev       # http://localhost:4321
pnpm --filter @seeband/site build     # static files in apps/site/dist
pnpm --filter @seeband/site typecheck # astro check
pnpm --filter @seeband/site test      # builds the site and checks its output
pnpm --filter @seeband/site serve     # builds it and previews it on port 4321, for the app's dev:all
```

| Path             | Holds                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------- |
| `src/strings.ts` | every string the site shows                                                                 |
| `src/layouts`    | `Base.astro`, with the shared header and footer; `Prose.astro` for formulas                 |
| `src/pages`      | one file per page; `conventions.mdx` and `guide.mdx` (MDX), `results-changed.md` (Markdown) |
| `markdown.mjs`   | remark-math and rehype-katex, which render formulas when the site is built                  |

**English only for now**, at `/`. Another language would get its own routes, and the shared header's language switch would then need to link to the page in that language, as a static page cannot read the language cookie.

**The icons** in `public/` serve every page of the site and of the app, as Caddy serves the site at the root: `favicon.svg` is the header's logo, and `favicon.ico` (16, 32 and 48 px) and `apple-touch-icon.png` (180 px) are drawn from it by `pnpm --filter @seeband/site icons`. Run that after changing the SVG, and commit what it writes.

**The header lists the same sections as the app's:** Overview, Model fit, Results and Conventions. Links from Markdown pages into the repository go to GitHub, as its files are not on the site.

**No script is needed.** Pages work with JavaScript turned off. The only script is the shared header's language handler, about 300 bytes, which does nothing with one language. Plotly and Pyodide are not loaded here, and the build test checks it.

**The user guide** (`/guide/`) is adapted from the desktop SeeBand's PDF guide (MIT). Its screenshots in `public/guide/` and the numbers it quotes come from `apps/web/scripts/capture-guide.mjs`, run against the app and API on the Fe2VAl0.9Si0.1 example; run it again when the screens change.

**The worked examples** (`/examples/`) walk through the three example sets of the desktop SeeBand. Their screenshots in `public/examples/` come from `apps/web/scripts/capture-examples.mjs`, which also prints each fit's start, status, RMSEs and parameters; the pages' numbers are copied from that output by hand, so after a change to the screens or the core, run it again and check each page against it.

**Search engines.** The build reads the public address from `SEEBAND_SITE_URL`, an http or https origin such as `https://seeband.example`; a path or anything else fails the build, as the site is served at the root. With it, each page gets a canonical link and `og:url`, `sitemap.xml` lists every page but the 404 page, and `robots.txt` keeps search engines out of the app's screens, the API and the app's licence texts (`APP_SCREENS` and `NOT_FOR_SEARCH_PREFIXES` in `src/strings.ts`; anchored, so that `/results` does not also close `/results-changed/`) and names the sitemap. A URL closed by `robots.txt` can still be listed from links alone, as its own `noindex` goes unread; an `X-Robots-Tag: noindex` header from the proxy for those paths would close that gap ([I1](https://github.com/pdasya/seeband-web/issues/53)). Without it, as for the prototype host until the move to the final host ([I6](https://github.com/pdasya/seeband-web/issues/72)), every page says `noindex`, `robots.txt` disallows everything and the sitemap is empty, as its addresses would have to be absolute. Every page has its own title, description and Open Graph tags either way, and the overview describes the app as a schema.org `SoftwareApplication` in JSON-LD. There is no `hreflang` while the site has one language. The build test checks both builds; Google's Rich Results test and Search Console wait for the public host.

**Formulas** in Markdown and MDX are rendered by KaTeX at build time, so a page gets HTML and CSS and no script. A page with formulas uses `Prose.astro`, the only layout that loads KaTeX's styles; in MDX, name it as `layout` in the frontmatter, with `title` and `description`. `tests/fixtures/math` builds such a page. The `katex` dependency, whose styles the layout loads, stays on the version `rehype-katex` renders with (0.16 now): their class names differ between versions, and a test fails if they part.

**Fonts** are Geist and Geist Mono from `packages/ui`, served by the site itself.

## Decisions on the overview

- **Data handling (F4, #4), 2026-11-17.** The overview says what the code supports: measurements go to the server, are used only for the calculation asked for and are not saved; the server's logs record route, status and duration, not data. It names no LLM summaries, as there are none. Revise it if that changes, and when I1 sets up the proxy's logging.
- **Hero illustration (F8, #8), 2026-11-17.** Option A of the design's `HeroOptions`: the E(k) sketch of two parabolic bands with E_g and E_F, inline SVG in `src/components/BandFigure.astro`. A sketch, not a calculation: its caption says it shows one DPB case and names the others (band 2 a valence band, overlapping bands, E_F inside a band). On a phone its labels grow and the edge labels and band kinds go.

## Lighthouse baseline

Home page, `astro preview`, Lighthouse 12.8.2, mobile with simulated throttling, headless Chrome for Testing on macOS, 2026-11-17, with the full overview (S2): performance 100, accessibility 100, best practices 100, SEO 100. First and largest contentful paint 1.2 s, total blocking time 0 ms, cumulative layout shift 0, 59 KiB transferred.
