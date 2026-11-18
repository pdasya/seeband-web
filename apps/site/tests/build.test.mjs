// Builds the site as production does, and checks what a browser gets: static HTML that needs
// no script, with no heavy library.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { createRequire } from "node:module";
import { dirname, join, relative } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

const SITE_DIR = fileURLToPath(new URL("..", import.meta.url));
const MATH_DIR = fileURLToPath(new URL("fixtures/math", import.meta.url));
// Astro's own script, run with this Node, as the shell shim in node_modules/.bin is not on every
// system or install layout.
const ASTRO = join(
  dirname(
    createRequire(join(SITE_DIR, "package.json")).resolve("astro/package.json"),
  ),
  "bin",
  "astro.mjs",
);
const outDir = mkdtempSync(join(tmpdir(), "seeband-site-build-"));
const mathOutDir = mkdtempSync(join(tmpdir(), "seeband-site-math-"));

function build(root, out) {
  const built = spawnSync(
    process.execPath,
    [ASTRO, "build", "--root", root, "--outDir", out],
    {
      cwd: SITE_DIR,
      encoding: "utf8",
      env: { ...process.env, ASTRO_TELEMETRY_DISABLED: "1" },
    },
  );
  assert.equal(built.status, 0, built.stderr + built.stdout);
}

function files(dir) {
  return readdirSync(dir, { recursive: true })
    .map((name) => join(dir, name))
    .filter((path) => statSync(path).isFile());
}

const page = (path) => readFileSync(join(outDir, path), "utf8");

before(() => {
  build(SITE_DIR, outDir);
  build(MATH_DIR, mathOutDir);
});

after(() => {
  rmSync(outDir, { recursive: true, force: true });
  rmSync(mathOutDir, { recursive: true, force: true });
});

test("has its pages in English, as static HTML", () => {
  for (const path of ["index.html", "404.html"]) {
    assert.match(page(path), /<html lang="en"/, path);
  }
  assert.match(
    page("index.html"),
    /<h1>Parabolic band models for transport measurements<\/h1>/,
  );
  assert.match(page("index.html"), /<link rel="icon" href="\/favicon.svg"/);
  assert.ok(statSync(join(outDir, "favicon.svg")).isFile());
  assert.match(
    page("index.html"),
    /<a href="\/"[^>]*aria-current="page"[^>]*>Overview<\/a>/,
  );
  // One language for now, so no switch, and no page in another.
  assert.doesNotMatch(page("index.html"), /sb-header__languages|hreflang/);
  assert.equal(
    files(outDir).some((path) => relative(outDir, path).startsWith("de/")),
    false,
  );
});

test("links to the app and the original SeeBand", () => {
  const html = page("index.html");
  assert.match(html, /class="button" href="\/fit"/);
  assert.match(html, /<a href="\/fit" class="sb-header__link">Model fit/);
  assert.match(html, /<a href="\/results" class="sb-header__link">Results/);
  assert.match(html, /href="https:\/\/github.com\/pdasya\/seeband-web"/);
  assert.match(html, /href="https:\/\/github.com\/xAngelswordx\/SeeBand"/);
  assert.match(
    html,
    /href="https:\/\/github.com\/pdasya\/seeband-web\/issues"/,
  );
});

const textOfPage = (html) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

/** The page's main content, without the shared header and footer. */
const mainOf = (html) => html.match(/<main[\s\S]*<\/main>/)?.[0] ?? "";
// Visible text, with tags and Astro's attributes out of the way.
const textOf = (html) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

test("the overview says where data go, and promises only what the app does", () => {
  const main = mainOf(page("index.html"));
  const text = textOf(main);
  // F4: the data go to the server, are used only for the calculation, and are not saved or logged.
  assert.match(
    text,
    /Your data Calculations run on our server, so your measurements are sent to it\./,
  );
  assert.match(text, /does not save them/);
  assert.match(text, /not your data/);
  // Not delivered, or no longer offered: the browser, AI summaries, residual plots, acPhDis.
  assert.doesNotMatch(
    text,
    /runs in the browser|\bAI\b|residuals|acPhDis|\[Repository/i,
  );
  // F8: the E(k) sketch, inline and labelled as one case, with no image file.
  assert.match(
    main,
    /<svg[^>]*role="img"[^>]*aria-label="Schematic of one DPB case/,
  );
  assert.match(text, /Schematic, not to scale/);
  assert.match(main, /href="\/fit\?demo=1"/);
  assert.match(main, /href="\/results-changed\/"/);
});

test("the overview's structure holds together", () => {
  const html = page("index.html");
  assert.equal(html.match(/<h1[\s>]/g)?.length, 1);
  const ids = new Set(
    [...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]),
  );
  const labelled = [...html.matchAll(/aria-labelledby="([^"]+)"/g)].map(
    (match) => match[1],
  );
  assert.ok(labelled.length >= 5);
  for (const id of labelled) {
    assert.ok(ids.has(id), id);
  }
  // A table that can scroll can be reached by keyboard.
  assert.match(html, /class="table-scroll"[^>]*tabindex="0"/);
});

test("has the Conventions and results-changed pages, linked from the header", () => {
  for (const path of ["index.html", "conventions/index.html"]) {
    assert.match(
      page(path),
      /<a href="\/conventions\/"[^>]*>Conventions<\/a>/,
      path,
    );
  }
  const conventions = page("conventions/index.html");
  assert.match(conventions, /<title>Conventions and model · SeeBand<\/title>/);
  assert.match(
    conventions,
    /<a href="\/conventions\/"[^>]*aria-current="page"/,
  );
  assert.match(
    conventions,
    /<h2[^>]*>Thermal conductivity and Lorenz number<\/h2>/,
  );
  assert.match(conventions, /href="\/results-changed\/"/);
  assert.match(page("results-changed/index.html"), /<table>/);
  // Links into the repository go to GitHub, as relative paths do not exist on the site.
  for (const path of ["conventions/index.html", "results-changed/index.html"]) {
    assert.doesNotMatch(page(path), /href="\.\.?\//, path);
    assert.match(
      page(path),
      /href="https:\/\/github.com\/pdasya\/seeband-web\/blob\/main\/packages\//,
      path,
    );
  }
});

test("Conventions renders its formulas, lists its sections and ties issues to the registry", () => {
  const conventions = page("conventions/index.html");
  // KaTeX at build time: math as HTML, no failures, and the page's own styles for it.
  assert.ok((conventions.match(/class="katex"/g) ?? []).length >= 40);
  assert.doesNotMatch(conventions, /katex-error/);
  // MathML stays beside the visible formula, for screen readers.
  assert.match(conventions, /class="katex-mathml"/);
  // Wide tables and formulas scroll in a box a keyboard can reach, and tables stay tables.
  const tables = (conventions.match(/<table>/g) ?? []).length;
  assert.ok(tables >= 5);
  assert.equal(
    (conventions.match(/<div class="scroll-box" tabindex="0"><table>/g) ?? [])
      .length,
    tables,
  );
  assert.match(conventions, /class="katex-display" tabindex="0"/);
  // Each section is in the side list, by its anchor.
  const anchors = [...conventions.matchAll(/<h2[^>]*\sid="([^"]+)"/g)].map(
    (m) => m[1],
  );
  assert.ok(anchors.length >= 10);
  for (const anchor of anchors) {
    assert.match(conventions, new RegExp(`<a href="#${anchor}">`), anchor);
  }
  // The registry's issues, each with its tracking issue; a core test checks they match it.
  for (const id of [
    "dpb_loop_degeneracy",
    "collapsed_m_eff",
    "no_chemical_potential",
    "hall_dis_no_reference",
    "interpolation_extrapolates",
  ]) {
    assert.match(conventions, new RegExp(`<code>${id}</code>`), id);
  }
  assert.match(conventions, /<h2 id="band-diagram">Band diagram<\/h2>/);
  // No mixed scattering is offered any more; the page says so where it names it.
  assert.match(textOfPage(conventions), /acPhDis[^.]*not offered/);
});

test("needs no script but the header's, and loads no heavy library", () => {
  const all = files(outDir);
  assert.deepEqual(
    all.filter((path) => path.endsWith(".js")),
    [],
    "no script files",
  );
  for (const path of all.filter((path) => path.endsWith(".html"))) {
    const html = readFileSync(path, "utf8");
    // Only the shared header's language script, which does nothing with one language.
    const scripts = html.match(/<script[\s\S]*?<\/script>/g) ?? [];
    assert.equal(scripts.length, 1, relative(outDir, path));
    assert.match(scripts[0], /seeband_language/);
    assert.ok(scripts[0].length < 1000, relative(outDir, path));
    assert.doesNotMatch(html, /plotly|pyodide/i, relative(outDir, path));
  }
});

test("serves its fonts itself, and asks no other host", () => {
  const css = files(outDir)
    .filter((path) => path.endsWith(".css"))
    .map((path) => readFileSync(path, "utf8"))
    .join("");
  assert.match(css, /Geist Variable/);
  assert.match(css, /url\(\/_astro\/geist-latin-wght-normal\.[\w-]+\.woff2\)/);
  for (const path of files(outDir).filter((p) => /\.(html|css)$/.test(p))) {
    assert.doesNotMatch(
      readFileSync(path, "utf8"),
      /(src|href)="?https?:\/\/(?!github\.com)|url\(["']?https?:/,
      relative(outDir, path),
    );
  }
  // KaTeX's styles and fonts come only with pages of text and formulas.
  const homeCss = [
    ...page("index.html").matchAll(/<link rel="stylesheet" href="([^"]+)"/g),
  ]
    .map((match) => readFileSync(join(outDir, match[1]), "utf8"))
    .join("");
  assert.doesNotMatch(homeCss, /KaTeX_Main|\.katex/);
});

test("renders formulas in MDX when built, with KaTeX's styles and no script", () => {
  const html = readFileSync(join(mathOutDir, "index.html"), "utf8");
  assert.match(html, /class="katex"/);
  assert.match(html, /class="katex-display"/);
  assert.match(
    html,
    /<annotation encoding="application\/x-tex">L = \\frac\{\\kappa_e\}\{\\sigma T\}/,
  );
  const css = files(mathOutDir)
    .filter((path) => path.endsWith(".css"))
    .map((path) => readFileSync(path, "utf8"))
    .join("");
  assert.match(css, /KaTeX_Main/);
  assert.equal(
    files(mathOutDir).filter((path) => path.endsWith(".js")).length,
    0,
  );
});
