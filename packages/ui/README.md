# packages/ui

Design tokens and the shared header, used by `apps/web`, and by `apps/site` from S1.

| File         | Holds                                                                   |
| ------------ | ----------------------------------------------------------------------- |
| `tokens.css` | the design's values as plain CSS variables, with no Tailwind needed     |
| `theme.css`  | the names Tailwind gives them, such as `bg-primary`. Needs `tokens.css` |
| `fonts.css`  | Geist and Geist Mono, from npm, served with the app                     |

The values come from the design, and chart accents are `--accent-blue`, `--accent-orange` and `--accent-teal`. Fonts are not loaded from Google Fonts, because a request to another host would tell it who visits.

## Header

`src/header` holds one header for two builds: `header.css`, with no build step in common, and a thin wrapper for each of React and Astro. Both take the same `HeaderModel`, and `tests/header.test.tsx` renders each, the Astro one with Astro itself, and compares their markup.

```tsx
import { SiteHeader } from "@seeband/ui/SiteHeader"; // React, with `renderLink` for a router
import SiteHeader from "@seeband/ui/SiteHeader.astro"; // Astro
import "@seeband/ui/header.css";
```

Links between the site and the app are plain links, as they are separate builds. A dev server that was running when `exports` changed in `package.json` needs a restart to find a new file.

**The language switch stays hidden until `languages` has more than one option,** as the app is in English only until [U3](https://github.com/pdasya/seeband-web/issues/36). `language.ts` holds the one cookie, `seeband_language`, read by both builds, and the Astro wrapper's small script writes it and reloads. A React user passes `onLanguageChange`. No page uses any of this yet.

**Not tried yet:** a real Astro site, which starts with S1, so neither the path from the site to the app and back, nor the script in a browser.
