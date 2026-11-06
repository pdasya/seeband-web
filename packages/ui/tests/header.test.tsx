import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import {
  LANGUAGE_COOKIE,
  languageCookie,
  readLanguage,
} from "../src/header/language";
import type { HeaderModel } from "../src/header/model";
import AstroHeader from "../src/header/SiteHeader.astro";
import { SiteHeader } from "../src/header/SiteHeader";

const MODEL: HeaderModel = {
  name: "SeeBand",
  stage: "web · prototype",
  navigationLabel: "Sections",
  links: [
    { id: "overview", label: "Overview", href: "/" },
    { id: "fit", label: "Model fit", href: "/app/fit", current: true },
  ],
};
const WITH_LANGUAGES: HeaderModel = {
  ...MODEL,
  languages: {
    label: "Language",
    current: "de",
    options: [
      { code: "en", label: "EN", name: "English" },
      { code: "de", label: "DE", name: "Deutsch" },
    ],
  },
};

/** Compares what a browser would build, as the two write the same markup differently. */
function normalise(html: string): string {
  const withoutAstro = html
    .replace(/<script[\s\S]*?<\/script>/g, "")
    .replace(/\sdata-astro-[\w-]*(="[^"]*")?/g, "")
    .replace(/<!--[\s\S]*?-->/g, "");
  return withoutAstro
    .replace(/>\s+</g, "><")
    .replace(
      /<(\w+)((?:\s+[\w:-]+(?:="[^"]*")?)+)(\s*\/?)>/g,
      (_, tag, attrs, end) => {
        const sorted = (attrs.match(/[\w:-]+(?:="[^"]*")?/g) ?? [])
          .sort()
          .join(" ");
        return `<${tag} ${sorted}${end.trim()}>`;
      },
    )
    .replace(/<path ([^>]*?)\s*\/?>(<\/path>)?/g, "<path $1/>")
    .trim();
}

async function renderAstro(model: HeaderModel): Promise<string> {
  const container = await AstroContainer.create();
  return container.renderToString(AstroHeader as never, {
    props: model as never,
  });
}

describe("both wrappers", () => {
  test.each([
    ["no language choice", MODEL],
    ["a language choice", WITH_LANGUAGES],
  ])("draw the same markup with %s", async (_, model) => {
    const astro = normalise(await renderAstro(model));
    const react = normalise(renderToStaticMarkup(<SiteHeader {...model} />));

    expect(astro).toBe(react);
    expect(react).toContain("sb-header__link--current");
    expect(react).toContain('aria-current="page"');
  });
});

describe("the language switch", () => {
  test.each([
    ["none", undefined],
    [
      "one language",
      {
        label: "Language",
        current: "en",
        options: [{ code: "en", label: "EN", name: "English" }],
      },
    ],
  ])("is left out with %s", (_, languages) => {
    const html = renderToStaticMarkup(
      <SiteHeader {...MODEL} {...(languages ? { languages } : {})} />,
    );

    expect(html).not.toContain("radiogroup");
  });

  test("marks the current language", () => {
    const html = renderToStaticMarkup(<SiteHeader {...WITH_LANGUAGES} />);

    expect(html).toContain('aria-checked="true" aria-label="Deutsch"');
    expect(html).toContain('aria-checked="false" aria-label="English"');
  });
});

describe("the language cookie", () => {
  const LANGUAGES = ["en", "de"] as const;

  test.each([
    ["", "en"],
    [`${LANGUAGE_COOKIE}=de`, "de"],
    [`other=1; ${LANGUAGE_COOKIE}=de; more=2`, "de"],
    [`${LANGUAGE_COOKIE}=fr`, "en"],
    [`not_${LANGUAGE_COOKIE}=de`, "en"],
  ])("from %j reads %s", (cookies, expected) => {
    expect(readLanguage(cookies, LANGUAGES, "en")).toBe(expected);
  });

  test("covers the site and the app, and lasts", () => {
    const cookie = languageCookie("de");

    expect(cookie).toContain(`${LANGUAGE_COOKIE}=de`);
    expect(cookie).toContain("Path=/");
    expect(cookie).toContain("SameSite=Lax");
    expect(cookie).toContain("Max-Age=31536000");
  });
});
