import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
const loadPackage = createRequire(import.meta.url);
const project = process.cwd();
const kit = path.resolve(import.meta.dirname, "..");
const file = path.join(kit, "fit-guide.html");
const dictionary = JSON.parse(
  fs.readFileSync(path.join(kit, "../band-parameter-labels.json")),
).fit_eligibility_rules;
const jsdom = loadPackage(path.join(project, "apps/web/node_modules/jsdom"));
const dom = new jsdom.JSDOM(fs.readFileSync(file, "utf8"), {
  runScripts: "dangerously",
});
const w = dom.window,
  d = w.document,
  one = (s) => d.querySelector(s),
  all = (s) => [...d.querySelectorAll(s)];
const states = (n, k, mech, m) => {
  const result = {},
    c = dictionary.common,
    p = dictionary.all_parabolic;
  const add = (s, a) => {
    if (a[m] !== "hidden") result[s] = a[m];
  };
  add("ef", c.fermi);
  add("mass", c.mass_1);
  for (let i = 1; i < n; i++) {
    add("gap" + i, c.edge_i_for_i_gt_1);
    add("massRatio" + i, c.mass_ratio_i_for_i_gt_1);
  }
  if (k >= 0) {
    add("alpha" + k, c.kane_alpha_if_present);
    for (let i = 0; i < n; i++)
      add(
        "amplitude" + i,
        dictionary.kane_present.per_band_absolute_prefactor[
          n === 1 ? "single_band" : "multiple_bands"
        ],
      );
  } else {
    add("scale", p.absolute_scale);
    for (let i = 1; i < n; i++)
      add(
        "ratio" + i,
        p.relative_weight_for_each_i_gt_1[
          { ac: "acPh", dis: "dis", ion: "ionized", mix: "acPhDis" }[mech]
        ],
      );
    if (mech === "mix")
      for (let i = 0; i < n; i++)
        add(
          "mix" + i,
          p.mixed_ratio_for_each_band[
            n === 1 ? "single_band" : "multiple_bands"
          ],
        );
  }
  return result;
};
const restore = (s, p = {}) =>
  w.dispatchEvent(
    new w.CustomEvent("openai:set_globals", {
      detail: {
        globals: { widgetState: { modelContent: s, privateContent: p } },
      },
    }),
  );
let checks = 0;
for (const n of [1, 2, 3])
  for (let mask = 0; mask < 2 ** n; mask++)
    for (let k = -1; k < n; k++) {
      const types = [0, 1, 2].map((i) => ((mask >> i) & 1) + (i === k ? 2 : 0));
      for (const mechanism of k < 0 ? ["ac", "dis", "ion", "mix"] : ["ac"])
        for (let selectedMode = 0; selectedMode < 3; selectedMode++) {
          restore({ n, types, mechanism, selectedMode });
          const actual = {};
          for (const r of all(".field")) {
            actual[r.dataset.field] = r.querySelector(".lock").disabled
              ? "manual"
              : "fit";
            assert.equal(r.querySelector(".field-caption").hidden, true);
            assert.ok(r.querySelector(".help").getAttribute("aria-controls"));
            assert.ok(!/^[A-G]$/.test(r.querySelector("label").textContent));
            assert.ok(!r.querySelector("input[type=number]").disabled);
          }
          assert.deepEqual(actual, states(n, k, mechanism, selectedMode));
          assert.equal(one("[data-field=ef] label").textContent, "EF");
          checks++;
        }
    }
let saved;
w.openai = {
  setWidgetState: (s) => {
    saved = s;
    return Promise.resolve();
  },
};
restore({ n: 2, types: [0, 1, 0], mechanism: "mix", selectedMode: 2 });
const field = (id, s) => one("[data-field=" + id + "] " + s);
const mode = (i) => one('[data-mode="' + i + '"]').click();
const set = (input, v) => {
  input.value = v;
  input.dispatchEvent(new w.Event("change"));
};
field("scale", ".help").click();
assert.equal(field("scale", ".field-caption").hidden, false);
field("mass", ".lock").click();
assert.equal(field("mass", ".lock").getAttribute("aria-pressed"), "true");
set(field("mass", "input"), "2.5");
mode(0);
assert.equal(field("mass", ".lock").disabled, true);
set(field("mass", "input"), "3");
mode(2);
assert.equal(field("mass", ".lock").getAttribute("aria-pressed"), "true");
assert.equal(field("mass", "input").value, "3");
one("#sb-bounds").click();
set(field("scale", ".limits label:first-child input"), "1500");
set(field("scale", ".limits label:last-child input"), "90000");
assert.equal(field("scale", "input[type=range]").hidden, false);
field("scale", ".lock").click();
mode(0);
assert.equal(field("scale", ".lock"), null);
mode(1);
assert.equal(field("scale", ".lock").getAttribute("aria-pressed"), "true");
restore(saved.modelContent, saved.privateContent);
assert.equal(field("scale", ".limits label:first-child input").value, "1500");
assert.equal(field("mass", "input").value, "3");
field("scale", ".lock").click();
assert.equal(field("scale", ".lock").getAttribute("aria-pressed"), "false");
assert.equal(one("#sb-fit table"), null);
assert.equal(one("#sb-guide").hidden, true);
const beforeLocks = all(".lock").map((b) => b.getAttribute("aria-pressed"));
one("[data-page=guide]").click();
assert.equal(one("#sb-fit").hidden, true);
assert.equal(one("#sb-guide").hidden, false);
assert.equal(one("#sb-guide table").textContent.includes("◆"), false);
one("[data-page=fit]").click();
assert.deepEqual(
  all(".lock").map((b) => b.getAttribute("aria-pressed")),
  beforeLocks,
);
assert.ok(!/[А-Яа-яЁё]/.test(fs.readFileSync(file, "utf8")));
one("#sb-add").click();
set(field("massRatio2", "input"), "4");
field("massRatio2", ".lock").click();
one("#sb-remove").click();
one("#sb-add").click();
assert.equal(field("massRatio2", "input").value, "1");
assert.equal(
  field("massRatio2", ".lock").getAttribute("aria-pressed"),
  "false",
);
assert.equal(one('[data-band="2"] [data-choice=Kane]').disabled, true);
set(one("#sb-scatter"), "ac");
assert.equal(one('[data-band="2"] [data-choice=Kane]').disabled, false);
one('[data-band="2"] [data-choice=Kane]').click();
assert.equal(one("#sb-model-name").textContent, "1 SKB + 2 SPB");
assert.ok(one('[data-band="0"] [data-choice=Kane]').disabled);
one('[data-band="2"] [data-choice=VB]').click();
assert.ok(field("alpha2", "input"));
one("#sb-remove").click();
assert.equal(one("#sb-model-name").textContent, "DPB");
one("#sb-remove").click();
assert.equal(one("#sb-remove").hidden, true);
for (const t of [
  [0, 1, 0],
  [1, 0, 0],
  [2, 1, 0],
  [1, 2, 0],
]) {
  restore({ n: 2, types: t, mechanism: "ac", selectedMode: 1 });
  assert.equal(field("gap1", "label").textContent, "Eg");
  assert.equal(field("gap1", "input").value, "0.09");
  one("#sb-bounds").click();
  set(field("gap1", ".limits label:first-child input"), "-0.2");
  set(field("gap1", ".limits label:last-child input"), "0.4");
  set(field("gap1", "input"), "-0.03");
  assert.equal(one("#sb-gap-readout").textContent, "Band overlap = 0.03 eV");
  mode(2);
  assert.equal(field("gap1", "input").value, "-0.03");
  assert.equal(field("gap1", ".limits label:first-child input").value, "-0.2");
  field("gap1", ".lock").click();
  one("#sb-add").click();
  assert.equal(+field("gap1", "input").value, t[0] % 2 ? 0.03 : -0.03);
  assert.equal(
    +field("gap1", ".limits label:first-child input").value,
    t[0] % 2 ? -0.4 : -0.2,
  );
  one("#sb-remove").click();
  assert.equal(field("gap1", ".lock").getAttribute("aria-pressed"), "true");
  set(field("gap1", "input"), "0");
  assert.equal(field("gap1", "label").textContent, "Eg");
}
restore({ n: 3, types: [0, 1, 1], mechanism: "ac", selectedMode: 0 });
set(field("gap1", "input"), "0.1");
set(field("gap2", "input"), "0.035");
assert.equal(one("#sb-gap-value").textContent, "0.035 eV");
restore({ n: 3, types: [1, 1, 1], mechanism: "ac", selectedMode: 2 });
assert.ok(one("#sb-gap-readout").hidden);
assert.ok(!all(".field label").some((l) => l.textContent === "Eg"));
for (const shape of [
  [1, 0, 1],
  [0, 1, 0],
  [3, 0, 1],
])
  for (const m of [0, 1, 2]) {
    restore({ n: 3, types: shape, mechanism: "ac", selectedMode: m });
    const v = shape[0] % 2 === 1 ? -1 : 1;
    set(field("gap1", "input"), String(v * 0.09));
    set(field("gap2", "input"), String(-v * 0.08));
    assert.equal(one("#sb-gap-value").textContent, "0.09 eV");
    set(field("gap2", "input"), String(v * 0.04));
    assert.equal(one("#sb-gap-value").textContent, "0.05 eV");
    assert.ok(
      one("#sb-gap-origin").textContent.includes("₃"),
      JSON.stringify([shape, m, one("#sb-gap-origin").textContent]),
    );
    set(field("gap2", "input"), "0");
    assert.ok(one("#sb-gap-origin").textContent.includes(" / "));
    set(field("gap2", "input"), String(v * 0.09));
    assert.equal(one("#sb-gap-value").textContent, "0 eV");
    set(field("gap2", "input"), String(v * 0.11));
    assert.equal(one("#sb-gap-value").textContent, "Closed");
    assert.match(one("#sb-gap-origin").textContent, /0.02 eV/);
    set(field("gap2", "input"), "");
    assert.equal(one("#sb-gap-value").textContent, "—");
  }
for (const t of [0, 1]) {
  restore({ n: 3, types: [t, t, t], mechanism: "ac", selectedMode: 0 });
  assert.equal(one("#sb-gap-value").textContent, "Undetermined");
}
console.log(
  "Signed gap, overlap, contact, extrema and reverse-order bounds passed.",
);
console.log(
  checks +
    " matrix states match JSON. Lock, editable manual value, hidden bounds, tooltips and restore passed.",
);
if (process.argv[2]) {
  (async () => {
    const { chromium } = loadPackage(
      path.join(project, "apps/web/node_modules/@playwright/test"),
    );
    const browser = await chromium.launch({
      channel: "chrome",
      headless: true,
    });
    try {
      const page = await browser.newPage({
        viewport: { width: 960, height: 900 },
        deviceScaleFactor: 1.5,
        colorScheme: "light",
      });
      await page.goto(pathToFileURL(file).href);
      await page.locator("#sb-gap-value").getByText("0.09 eV").waitFor();
      await page
        .locator("#sb-desktop-parameters")
        .screenshot({ path: process.argv[2] });
      await page.getByRole("button", { name: "Guide", exact: true }).click();
      assert.equal(await page.getByRole("table").count(), 1);
      await page.getByRole("button", { name: "Fit", exact: true }).click();
      assert.equal(await page.getByRole("table").count(), 0);
      await page.setViewportSize({ width: 320, height: 850 });
      assert.ok(
        await page.evaluate(
          () => globalThis.document.documentElement.scrollWidth <= 320,
        ),
        "mobile overflow",
      );
      await page.locator("[data-field=gap1] .help").click();
      await page
        .locator("[data-field=gap1] .field-caption")
        .waitFor({ state: "visible" });
      console.log(
        "Chrome rendered at 960 and 320 px; no overflow, help opens.",
      );
    } finally {
      await browser.close();
    }
  })().catch((e) => {
    console.error(e.message);
    process.exitCode = 1;
  });
}
