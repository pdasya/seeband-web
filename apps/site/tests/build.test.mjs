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
    /Band structure from transport measurements/,
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
});

test("the overview says where data go, and promises only what the app does", () => {
  const html = page("index.html");
  // F4: the data go to the server, are used only for the calculation, and are not saved or logged.
  assert.match(html, /<h2 id="data">Your data<\/h2>/);
  assert.match(html, /your measurements are sent to it/);
  assert.match(html, /does not save them/);
  assert.match(html, /not your data/);
  assert.doesNotMatch(html, /runs in the browser/i);
  // Not delivered yet, or no longer offered.
  assert.doesNotMatch(html, /\bAI\b|summary|acPhDis|\[Repository/i);
  // F8: the E(k) sketch, inline and labelled, with no script or image file.
  assert.match(
    html,
    /<svg viewBox="0 0 480 320" role="img" aria-label="Schematic of two parabolic bands/,
  );
  assert.match(html, /href="\/fit\?demo=1"/);
  assert.match(html, /href="\/results-changed\/"/);
  assert.match(
    html,
    /href="https:\/\/github.com\/pdasya\/seeband-web\/issues"/,
  );
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
  assert.match(
    conventions,
    /<title>Calculation conventions · SeeBand<\/title>/,
  );
  assert.match(
    conventions,
    /<a href="\/conventions\/"[^>]*aria-current="page"/,
  );
  assert.match(conventions, /<h2[^>]*>Lorenz number<\/h2>/);
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
