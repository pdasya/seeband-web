// Builds the app as production does, and checks what a browser would get at /app.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
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

test("every asset is requested under /app/", () => {
  const paths = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((m) => m[1]);

  assert.ok(paths.length >= 2);
  for (const path of paths) {
    assert.match(path, /^\/app\/assets\//);
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
    assert.match(match[1], /^\/app\/assets\//);
  }
});

test("the fonts' licenses are served with them", () => {
  for (const name of ["Geist-OFL.txt", "Geist-Mono-OFL.txt"]) {
    const license = readFileSync(join(outDir, "licenses", name), "utf8");
    assert.match(license, /SIL Open Font License/);
  }
});

test("the root font size stays, as Tailwind's sizes in rem would otherwise shrink", () => {
  for (const match of css.matchAll(
    /(?:^|})\s*(?:html|:root)[^{]*\{([^}]*)\}/g,
  )) {
    assert.doesNotMatch(match[1], /(?:^|;)\s*font-size:/);
  }
});

test("the design's values reach the styles", () => {
  for (const value of [
    "#18181b",
    "#e4e4e7",
    "#f4f4f5",
    "#71717a",
    "#2563eb",
    "#ea580c",
    "#0d9488",
    "--radius-card:12px",
    "--radius-group:8px",
    "--radius-control:6px",
  ]) {
    assert.ok(css.replaceAll(" ", "").includes(value), value);
  }
});
