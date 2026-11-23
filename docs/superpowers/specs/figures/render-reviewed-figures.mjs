// Run from the repository root: node docs/superpowers/specs/figures/render-reviewed-figures.mjs
// These are synthetic design illustrations, not calculated or fitted results.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require(
  path.resolve("apps/web/node_modules/@playwright/test"),
);
const directory = path.dirname(fileURLToPath(import.meta.url));
const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 960, height: 900 },
    deviceScaleFactor: 1.5,
    colorScheme: "light",
  });
  const kRefPerAngstrom = 1;
  const kRefPerNanometre = 10;
  assert.equal(kRefPerAngstrom * 10, kRefPerNanometre);
  // The earlier sketch used reciprocal angstroms; k_ref = 1 Å⁻¹ preserves
  // its geometry. A reciprocal-nm coordinate divides by 10.
  assert.equal(0.6 / kRefPerNanometre, 0.06);
  const panels = [144, 867]
    .map((left, panel) => {
      const cx = left + 312;
      const y = (energyMeV) => 231 - energyMeV * 1.344;
      const curve = (mass, sign, edge, color) => {
        const points = Array.from({ length: 201 }, (_, i) => {
          const kappa = -0.085 + (0.17 * i) / 200;
          const physicalK = kappa * kRefPerAngstrom;
          const energy = edge + sign * (3809.98212 / mass) * physicalK ** 2;
          return `${cx + (kappa / 0.085) * 283},${y(energy)}`;
        });
        return `<polyline points="${points.join(" ")}" fill="none" stroke="${color}" stroke-width="5.5"/>`;
      };
      return `<text x="${left}" y="78" font-size="30" font-weight="700">${panel ? "(b) 20 meV gap" : "(a) Touching band edges"}</text>
      <path d="M${left},90 V450 H${left + 624}" fill="none" stroke="#a8b2c2" stroke-width="1.7"/>
      ${[100, 0, -100].map((e) => `<path d="M${left - 8},${y(e)}h8" stroke="black" stroke-width="1.5"/>${panel ? "" : `<text x="${left - 15}" y="${y(e) + 8}" text-anchor="end">${e < 0 ? "−" + -e : e}</text>`}`).join("")}
      ${curve(0.7, -1, 0, "#255fbc")}${curve(0.4, 1, panel ? 20 : 0, "#bd4500")}${curve(0.9, -1, -120, "#00877d")}
      <path d="M${left},${y(panel ? 10 : 0)}h624" stroke="#293244" stroke-width="2.8" stroke-dasharray="11 9"/>
      <g data-axis="k"><text x="${cx}" y="495" text-anchor="middle" font-style="italic">k <tspan font-style="normal">(dimensionless)</tspan></text></g>`;
    })
    .join("");
  await page.setViewportSize({ width: 1520, height: 608 });
  await page.setContent(`<svg xmlns="http://www.w3.org/2000/svg" width="1520" height="608" style="font-family:Arial,sans-serif;font-size:24px;background:white">
    ${panels}<text transform="translate(52 300) rotate(-90)" text-anchor="middle" font-style="italic">E − E₁ <tspan font-style="normal">(meV)</tspan></text>
    <path d="M440,574h50" stroke="#255fbc" stroke-width="5.5"/><text x="505" y="582">1 · VB</text>
    <path d="M612,574h50" stroke="#bd4500" stroke-width="5.5"/><text x="677" y="582">2 · CB</text>
    <path d="M785,574h50" stroke="#00877d" stroke-width="5.5"/><text x="850" y="582">3 · VB</text>
    <path d="M960,574h50" stroke="#293244" stroke-width="2.8" stroke-dasharray="11 9"/><text x="1025" y="582" font-style="italic">E<tspan baseline-shift="sub" font-size="17">F</tspan></text>
    </svg><style>body{margin:0}</style>`);
  const horizontalLabels = await page
    .locator('g[data-axis="k"] text')
    .allTextContents();
  assert.deepEqual(horizontalLabels, [
    "k (dimensionless)",
    "k (dimensionless)",
  ]);
  const numbersBelowPlots = await page
    .locator("svg text[y]")
    .evaluateAll(
      (nodes) =>
        nodes.filter(
          (el) =>
            Number(el.getAttribute("y")) >= 450 &&
            Number(el.getAttribute("y")) < 550 &&
            /[0-9]/.test(el.textContent),
        ).length,
    );
  assert.equal(numbersBelowPlots, 0);
  await page.locator("svg").screenshot({
    path: path.join(directory, "three-band-edges.png"),
    scale: "css",
  });
  if (!process.argv.includes("--edges-only")) {
    await page.setViewportSize({ width: 960, height: 900 });
    await page.goto(
      pathToFileURL(
        path.join(directory, "../band-composition-v0.7/fit-guide.html"),
      ).href,
    );
    const restore = async (modelContent) =>
      page.evaluate((s) => {
        globalThis.dispatchEvent(
          new globalThis.CustomEvent("openai:set_globals", {
            detail: {
              globals: { widgetState: { modelContent: s, privateContent: {} } },
            },
          }),
        );
      }, modelContent);
    const capture = async (name) =>
      page
        .locator("#sb-desktop-parameters")
        .screenshot({ path: path.join(directory, name) });
    await restore({
      n: 2,
      types: [0, 1, 0],
      mechanism: "mix",
      selectedMode: 1,
    });
    await page.locator('[data-field="ef"] .lock').click();
    assert.equal(
      await page
        .locator('[data-field="ef"] .lock')
        .getAttribute("aria-pressed"),
      "true",
    );
    assert.match(
      await page.locator('[data-field="scale"] label').innerText(),
      /acPh/,
    );
    await capture("parameters-fit-locks.png");
    await page.getByRole("button", { name: "Guide", exact: true }).click();
    await capture("parameters-guide-matrix.png");
    await restore({ n: 3, types: [1, 0, 1], mechanism: "ac", selectedMode: 2 });
    assert.equal(await page.locator("#sb-gap-value").innerText(), "0,09 eV");
    await capture("three-band-gap-parameters.png");
  }
} finally {
  await browser.close();
}
