import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, test } from "vitest";

import { AppHeader } from "./AppHeader";

describe("the header's link to the overview", () => {
  test("is named for a screen reader by what it shows, then where it goes", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/fit"]}>
        <AppHeader />
      </MemoryRouter>,
    );
    const label = /class="sb-header__home"[^>]*aria-label="([^"]*)"/.exec(
      html,
    )?.[1];
    const name = /<span class="sb-header__name">([^<]*)<\/span>/.exec(
      html,
    )?.[1];

    // WCAG 2.5.3: a voice command naming the visible text must find the link.
    expect(name).toBeTruthy();
    expect(label?.startsWith(name ?? "\u0000")).toBe(true);
    expect(label).not.toBe(name);
  });
});
