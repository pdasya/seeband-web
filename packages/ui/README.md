# packages/ui

Design tokens, used by `apps/web`, and by `apps/site` from S1. The shared header and the language switch come with U6.

| File         | Holds                                                                   |
| ------------ | ----------------------------------------------------------------------- |
| `tokens.css` | the design's values as plain CSS variables, with no Tailwind needed     |
| `theme.css`  | the names Tailwind gives them, such as `bg-primary`. Needs `tokens.css` |
| `fonts.css`  | Geist and Geist Mono, from npm, served with the app                     |

The values come from the design, and chart accents are `--accent-blue`, `--accent-orange` and `--accent-teal`. Fonts are not loaded from Google Fonts, because a request to another host would tell it who visits.
