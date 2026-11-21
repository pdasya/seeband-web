# packages/ui

Design tokens and the shared header, used by `apps/web` and `apps/site`.

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
import "@seeband/ui/tokens.css"; // needed: the header takes its colours and width from these
import "@seeband/ui/header.css";
```

**The logo and the name are one link to the overview,** `homeHref` (`/` by default). `homeLabel` names it for a screen reader and starts with the visible name, such as `SeeBand, overview`; the stage badge stays outside the link.

Links between the site and the app are plain links, as they are separate builds. A dev server that was running when `exports` changed in `package.json` needs a restart to find a new file.

**The language switch stays hidden until `languages` has more than one option,** as the app is in English only until [U3](https://github.com/pdasya/seeband-web/issues/36). Its options are plain buttons with `aria-pressed`. `language.ts` holds the one cookie, `seeband_language`, and `readLanguage` for the app to read it. A React user passes `onLanguageChange`.

**The switch does not yet change a static page.** The Astro wrapper's script writes the cookie and reloads, but a static page cannot read a cookie, so the same text comes back. [S1](https://github.com/pdasya/seeband-web/issues/52) plans separate `en` and `de` routes, so the switch there must also go to the page in that language, and mark the current language from its route.

**Built in a real Astro site** in `apps/site`, with `tokens.css` imported before `header.css`. The language script has not run in a browser with a choice yet, as the site is in English only.
