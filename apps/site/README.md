# apps/site

The public pages, built with Astro as static HTML for Caddy to serve at `/`. The app is a separate build on the same origin at `/fit` and `/results`, with its files under `/assets/`; the site's are under `/_astro/`, so the two do not collide. Links between them are plain links.

```sh
pnpm --filter @seeband/site dev       # http://localhost:4321
pnpm --filter @seeband/site build     # static files in apps/site/dist
pnpm --filter @seeband/site typecheck # astro check
pnpm --filter @seeband/site test      # builds the site and checks its output
```

| Path             | Holds                                                                       |
| ---------------- | --------------------------------------------------------------------------- |
| `src/strings.ts` | every string the site shows                                                 |
| `src/layouts`    | `Base.astro`, with the shared header and footer; `Prose.astro` for formulas |
| `src/pages`      | one file per page; `conventions.md` and `results-changed.md` are Markdown   |
| `markdown.mjs`   | remark-math and rehype-katex, which render formulas when the site is built  |

**English only for now**, at `/`. Another language would get its own routes, and the shared header's language switch would then need to link to the page in that language, as a static page cannot read the language cookie.

**The header lists the same sections as the app's:** Overview, Model fit, Results and Conventions. Links from Markdown pages into the repository go to GitHub, as its files are not on the site.

**No script is needed.** Pages work with JavaScript turned off. The only script is the shared header's language handler, about 300 bytes, which does nothing with one language. Plotly and Pyodide are not loaded here, and the build test checks it.

**Formulas** in Markdown and MDX are rendered by KaTeX at build time, so a page gets HTML and CSS and no script. A page with formulas uses `Prose.astro`, the only layout that loads KaTeX's styles; in MDX, name it as `layout` in the frontmatter, with `title` and `description`. `tests/fixtures/math` builds such a page.

**Fonts** are Geist and Geist Mono from `packages/ui`, served by the site itself.

## Decisions on the overview

- **Data handling (F4, #4), 2026-11-17.** The overview says what the code supports: measurements go to the server, are used only for the calculation asked for and are not saved; the server's logs record route, status and duration, not data. It names no LLM summaries, as there are none. Revise it if that changes, and when I1 sets up the proxy's logging.
- **Hero illustration (F8, #8), 2026-11-17.** Option A of the design's `HeroOptions`: the E(k) sketch of two parabolic bands with E_g and E_F, inline SVG in `src/components/BandFigure.astro`. A sketch, not a calculation: its caption says it shows one DPB case and names the others (band 2 a valence band, overlapping bands, E_F inside a band). On a phone its labels grow and the edge labels and band kinds go.

## Lighthouse baseline

Home page, `astro preview`, Lighthouse 12.8.2, mobile with simulated throttling, headless Chrome for Testing on macOS, 2026-11-17, with the full overview (S2): performance 100, accessibility 100, best practices 100, SEO 100. First and largest contentful paint 1.2 s, total blocking time 0 ms, cumulative layout shift 0, 59 KiB transferred.
