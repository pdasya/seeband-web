# apps/web

The application served at `/app`: Vite, React and TypeScript. It shows data and results and holds no physics formulas.

```sh
pnpm --filter @seeband/web dev      # http://localhost:5173/app/
pnpm --filter @seeband/web build    # into apps/web/dist, every asset under /app/
pnpm --filter @seeband/web preview  # the production build at /app/
```

The page is a sample of the base components, to compare with the design. U2 replaces it, and U3 translates its text.

## Base components

`src/components/ui` holds Button, Input, Select, Switch, Slider, Tabs, Table, Badge and Alert. They are copies from [shadcn/ui](https://ui.shadcn.com), and they are ours to change. They differ from upstream, to match the design:

- Sizes, radii and colours are the design's. Badge has the status variants and Alert a `warning` variant.
- There are no dark variants, as the design has none.
- Focus comes from one rule in `src/index.css`, the design's outline, rather than a ring on each component. Select's options draw it inside themselves, as their menu would clip it. Transitions cover colours only, so that the outline appears at once.
- Slider with no value has one thumb, as Radix treats it. Upstream draws a second one with no value.
- Slider puts `aria-label` and `aria-labelledby` on its thumb, which is what has the role of slider. Upstream leaves them on the root, where a screen reader does not find them.
- Slider is a Radix slider with the design's colours and size. The design uses the browser's own range input, so the two differ a little in look.

**Rem stays 16 px.** The design's text is 14 px, set on `body`. Tailwind's sizes are in rem, so a smaller root makes a 36 px button 31.5 px.

## Adding a component

The `shadcn` skill in `apps/web/.claude/skills` is pinned to this version of the CLI. See [`THIRD_PARTY.md`](../../.claude/skills/THIRD_PARTY.md).

```sh
cd apps/web
pnpm dlx shadcn@4.23.0 add <name> --dry-run
```

**Check the result before keeping it.** With version 4.23.0, the registry's components import `cn` from the npm package `cn`, which shadcn publishes as a replacement for `clsx` and `tailwind-merge`, and the CLI installs it. This project keeps those two in `src/lib/utils.ts`, as `cn` is at 0.5 and its last release was days old when this was written. On 14 sample calls, the two gave the same classes. So after adding, change the import to `@/lib/utils`, run `pnpm --filter @seeband/web remove cn`, and apply the differences above. To move to `cn` later, change that import in `src/components/ui`, and remove `src/lib/utils.ts`.
