// Builds the app as production does, and checks what a browser would get.
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
import { join } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

const APP_DIR = fileURLToPath(new URL("..", import.meta.url));
const outDir = mkdtempSync(join(tmpdir(), "seeband-web-build-"));
let html;
let assets;
let css;

before(() => {
  const vite = join(APP_DIR, "node_modules", ".bin", "vite");
  const built = spawnSync(
    vite,
    ["build", "--outDir", outDir, "--emptyOutDir"],
    {
      cwd: APP_DIR,
      encoding: "utf8",
    },
  );
  assert.equal(built.status, 0, built.stderr);
  html = readFileSync(join(outDir, "index.html"), "utf8");
  assets = readdirSync(join(outDir, "assets"));
  const cssFile = assets.find((name) => name.endsWith(".css"));
  css = readFileSync(join(outDir, "assets", cssFile), "utf8");
});

after(() => rmSync(outDir, { recursive: true, force: true }));

test("every asset is requested under /assets/", () => {
  const paths = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((m) => m[1]);

  assert.ok(paths.length >= 2);
  for (const path of paths) {
    assert.match(path, /^\/assets\//);
  }
});

test("the fonts are served with the app, not from another host", () => {
  const fonts = assets.filter((name) => name.endsWith(".woff2"));

  assert.ok(fonts.some((name) => name.toLowerCase().includes("geist-latin")));
  assert.ok(
    fonts.some((name) => name.toLowerCase().includes("geist-mono-latin")),
  );
  for (const text of [html, css]) {
    assert.doesNotMatch(text, /fonts\.(googleapis|gstatic)\.com/);
  }
  for (const match of css.matchAll(/url\(([^)]+\.woff2)\)/g)) {
    assert.match(match[1], /^\/assets\//);
  }
});

test("the fonts' licenses are served with them", () => {
  for (const name of ["Geist-OFL.txt", "Geist-Mono-OFL.txt"]) {
    const license = readFileSync(join(outDir, "licenses", name), "utf8");
    assert.match(license, /SIL Open Font License/);
  }
});

test("the system's dark setting changes nothing, as there are no dark tokens", () => {
  assert.doesNotMatch(css, /prefers-color-scheme:\s*dark/);
});

test("Plotly loads on its own, and the test page is not built", () => {
  const sizeOf = (name) => statSync(join(outDir, "assets", name)).size;
  const scripts = assets.filter((name) => name.endsWith(".js"));
  const entry = html.match(/src="\/assets\/([^"]+\.js)"/)?.[1];
  const plotly = scripts.find((name) => name.startsWith("plotly"));

  assert.ok(plotly, scripts.join());
  assert.notEqual(entry, plotly);
  assert.ok(sizeOf(plotly) > 1_000_000);
  assert.ok(sizeOf(entry) < 1_000_000, String(sizeOf(entry)));
  assert.doesNotMatch(html, /plotly/);
  assert.ok(!assets.some((name) => name.includes("fixture")));
});

test("the root font size stays, as Tailwind's sizes in rem would otherwise shrink", () => {
  for (const match of css.matchAll(
    /(?:^|})\s*(?:html|:root)[^{]*\{([^}]*)\}/g,
  )) {
    assert.doesNotMatch(match[1], /(?:^|;)\s*font-size:/);
  }
});

// This shows that the tokens are built in, not that a component uses them.
test("the design's tokens are in the styles", () => {
  for (const value of [
    "#18181b",
    "#e4e4e7",
    "#f4f4f5",
    "#71717a",
    "#2563eb",
    "#ea580c",
    "#0d9488",
  ]) {
    assert.ok(css.replaceAll(" ", "").includes(value), value);
  }
});
