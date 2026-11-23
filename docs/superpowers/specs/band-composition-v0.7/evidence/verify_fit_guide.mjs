import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
const loadPackage = createRequire(import.meta.url);
const project = process.cwd();
const kit = path.resolve(import.meta.dirname, "..");
const file = process.env.FIT_GUIDE_FILE ?? path.join(kit, "fit-guide.html");
const labels = JSON.parse(
  fs.readFileSync(path.join(kit, "../band-parameter-labels.json")),
);
const dictionary = labels.fit_eligibility_rules;
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
assert.ok(!/\p{Script=Cyrillic}/u.test(fs.readFileSync(file, "utf8")));
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
// Item 8: exercise edits through the rendered controls, without depending on
// the private snapshot's parameter-key format.
function verifyBandTransitions(w) {
  const d = w.document;
  const one = (selector) => d.querySelector(selector);
  const field = (id, selector) => one('[data-field="' + id + '"] ' + selector);
  const mode = (i) => one('[data-mode="' + i + '"]').click();
  const set = (input, value) => {
    input.value = value;
    input.dispatchEvent(new w.Event("change"));
  };
  const equal = (actual, expected, message = "DOM state matches") => {
    if (JSON.stringify(actual) !== JSON.stringify(expected))
      throw new Error(
        message +
          ": expected " +
          JSON.stringify(expected) +
          ", received " +
          JSON.stringify(actual),
      );
  };
  const ok = (actual, message) => equal(Boolean(actual), true, message);
  const restore = (modelContent, privateContent = {}) =>
    w.dispatchEvent(
      new w.CustomEvent("openai:set_globals", {
        detail: { globals: { widgetState: { modelContent, privateContent } } },
      }),
    );
  let saved;
  w.openai = {
    setWidgetState: (snapshot) => {
      saved = snapshot;
      return Promise.resolve();
    },
  };
  const choose = (band, choice) =>
    one('[data-band="' + band + '"] [data-choice="' + choice + '"]').click();
  const bounds = (id) => [
    field(id, ".limits label:first-child input"),
    field(id, ".limits label:last-child input"),
  ];
  const edit = (id, value, low, high, locked = true) => {
    const pair = bounds(id);
    set(pair[0], String(low));
    set(pair[1], String(high));
    set(field(id, "input"), String(value));
    if ((field(id, ".lock").getAttribute("aria-pressed") === "true") !== locked)
      field(id, ".lock").click();
  };
  const expectField = (id, value, low, high, locked = true, forced = false) => {
    ok(field(id, "input"), id + " is visible");
    equal(+field(id, "input").value, value, id + " value survives transition");
    equal(
      bounds(id).map((input) => +input.value),
      [low, high],
      id + " bounds survive transition",
    );
    equal(
      field(id, ".lock").getAttribute("aria-pressed"),
      String(locked),
      id + " lock survives transition",
    );
    equal(field(id, ".lock").disabled, forced, id + " manual eligibility");
  };
  restore({ n: 3, types: [0, 1, 0], mechanism: "ac", selectedMode: 2 });
  one("#sb-bounds").click();
  edit("ef", -0.045, -0.3, 0.2);
  edit("mass", 2.7, 0.4, 7);
  edit("gap1", 0.13, -0.25, 0.45);
  edit("gap2", -0.07, -0.35, 0.2, false);
  edit("massRatio1", 3.2, 0.3, 8);
  edit("massRatio2", 4.4, 0.5, 9, false);
  edit("scale", 27000, 1500, 90000);
  edit("ratio1", 2.2, 0.2, 6);
  edit("ratio2", 5.5, 0.6, 10, false);
  for (const [band, choice] of [
    [1, "VB"],
    [0, "CB"],
    [2, "CB"],
  ]) {
    choose(band, choice);
    expectField("ef", -0.045, -0.3, 0.2);
    expectField("mass", 2.7, 0.4, 7);
    expectField("gap1", 0.13, -0.25, 0.45);
    expectField("gap2", -0.07, -0.35, 0.2, false);
    expectField("massRatio1", 3.2, 0.3, 8);
    expectField("massRatio2", 4.4, 0.5, 9, false);
    expectField("scale", 27000, 1500, 90000);
    expectField("ratio1", 2.2, 0.2, 6);
    expectField("ratio2", 5.5, 0.6, 10, false);
  }
  choose(1, "Kane");
  expectField("amplitude0", 27000, 1500, 90000);
  expectField("gap1", 0.13, -0.25, 0.45);
  expectField("gap2", -0.07, -0.35, 0.2, false);
  expectField("massRatio1", 3.2, 0.3, 8);
  expectField("massRatio2", 4.4, 0.5, 9, false);
  edit("alpha1", 1.8, 0.2, 4);
  edit("amplitude0", 12000, 100, 50000);
  edit("amplitude1", 23000, 200, 60000, false);
  edit("amplitude2", 34000, 300, 70000);
  mode(0);
  expectField("mass", 2.7, 0.4, 7, true, true);
  expectField("amplitude1", 23000, 200, 60000, true, true);
  set(field("amplitude1", "input"), "24000");
  mode(2);
  expectField("amplitude1", 24000, 200, 60000, false);
  choose(1, "CB");
  expectField("alpha1", 1.8, 0.2, 4);
  expectField("amplitude0", 12000, 100, 50000);
  expectField("amplitude1", 24000, 200, 60000, false);
  expectField("amplitude2", 34000, 300, 70000);
  choose(1, "Parabolic");
  equal(field("alpha1", "input"), null);
  expectField("scale", 12000, 100, 50000);
  expectField("ratio1", 2.2, 0.2, 6);
  choose(1, "Kane");
  expectField("alpha1", 1.8, 0.2, 4);
  expectField("amplitude1", 24000, 200, 60000, false);
  // The host serializes widget state when reopening the prototype.
  const savedSnapshot = () => JSON.parse(JSON.stringify(saved));
  const snapshot = savedSnapshot();
  restore({ n: 1, types: [0, 0, 0], mechanism: "dis", selectedMode: 0 });
  restore(snapshot.modelContent, snapshot.privateContent);
  expectField("alpha1", 1.8, 0.2, 4);
  expectField("massRatio2", 4.4, 0.5, 9, false);
  expectField("amplitude1", 24000, 200, 60000, false);
  one("#sb-remove").click();
  one("#sb-add").click();
  equal(field("massRatio2", "input").value, "1");
  equal(
    bounds("massRatio2").map((input) => input.value),
    ["", ""],
  );
  equal(field("massRatio2", ".lock").getAttribute("aria-pressed"), "false");
  expectField("alpha1", 1.8, 0.2, 4);
  expectField("massRatio1", 3.2, 0.3, 8);

  // Moving Kane must not reuse a prefactor with a different physical unit.
  choose(1, "Parabolic");
  choose(0, "Kane");
  equal(field("amplitude0", "input").value, "");
  equal(field("amplitude1", "input").value, "");
  edit("alpha0", 0.6, 0.1, 2, false);
  edit("amplitude0", 81000, 800, 180000, false);
  edit("amplitude1", 15000, 150, 75000);
  choose(0, "Parabolic");
  expectField("scale", 12000, 100, 50000);
  choose(1, "Kane");
  expectField("alpha1", 1.8, 0.2, 4);
  expectField("amplitude1", 24000, 200, 60000, false);
  choose(1, "Parabolic");
  choose(0, "Kane");
  expectField("alpha0", 0.6, 0.1, 2, false);
  expectField("amplitude0", 81000, 800, 180000, false);
  expectField("amplitude1", 15000, 150, 75000);

  restore({ n: 2, types: [0, 1, 0], mechanism: "ac", selectedMode: 2 });
  one("#sb-bounds").click();
  edit("gap1", -0.03, -0.2, 0.4);
  choose(1, "Kane");
  expectField("gap1", -0.03, -0.2, 0.4);
  choose(1, "Parabolic");
  expectField("gap1", -0.03, -0.2, 0.4);
  choose(0, "CB");
  expectField("gap1", -0.03, -0.2, 0.4);
  choose(1, "VB");
  expectField("gap1", 0.03, -0.4, 0.2);
  const reversedSnapshot = savedSnapshot();
  restore(reversedSnapshot.modelContent, reversedSnapshot.privateContent);
  expectField("gap1", 0.03, -0.4, 0.2);
  choose(0, "VB");
  expectField("gap1", -0.03, -0.2, 0.4);
  choose(1, "CB");
  expectField("gap1", -0.03, -0.2, 0.4);

  // Literal legacy input is the compatibility boundary. Expectations still
  // observe DOM state, never the replacement snapshot's internal keys.
  const legacy = {
    values: {
      "scale/0-0/ac": "11000",
      "amplitude0/0-0": "22000",
      "gap1/0-1": "0.08",
      "gap1/0-3": "0.14",
      "mass/1-1": "8",
      "mass/0-0": "2.6",
    },
    limits: {
      "scale/0-0/ac": ["110", "77000"],
      "amplitude0/0-0": ["220", "88000"],
      "gap1/0-1": ["-0.1", "0.3"],
      "gap1/0-3": ["-0.2", "0.5"],
      "mass/1-1": ["1", "10"],
      "mass/0-0": ["0.4", "6"],
    },
    held: ["scale/0-0/ac", "gap1/0-1", "mass/1-1"],
    editBounds: true,
  };
  restore({ n: 2, types: [0, 3, 0], mechanism: "ac", selectedMode: 2 }, legacy);
  expectField("amplitude0", 22000, 220, 88000, false);
  expectField("gap1", 0.14, -0.2, 0.5, false);
  expectField("mass", 2.6, 0.4, 6, false);
  // A user action saves the restored state through the public host callback.
  mode(1);
  const migratedSnapshot = savedSnapshot();
  restore(migratedSnapshot.modelContent, migratedSnapshot.privateContent);
  expectField("amplitude0", 22000, 220, 88000, false);
  expectField("gap1", 0.14, -0.2, 0.5, false);
  restore({ n: 2, types: [0, 1, 0], mechanism: "ac", selectedMode: 2 }, legacy);
  expectField("scale", 11000, 110, 77000);
  expectField("gap1", 0.08, -0.1, 0.3);
  expectField("mass", 2.6, 0.4, 6, false);
}
// Item 9: configuration cautions and opt-in illustrative results are distinct.
// This same DOM contract runs under jsdom and the installed Chrome browser.
function verifyIdentifiability(w, copy) {
  const d = w.document;
  const one = (selector) => d.querySelector(selector);
  const equal = (actual, expected, message) => {
    if (JSON.stringify(actual) !== JSON.stringify(expected))
      throw new Error(
        message +
          ": expected " +
          JSON.stringify(expected) +
          ", received " +
          JSON.stringify(actual),
      );
  };
  const visible = (element) =>
    Boolean(
      element &&
      !element.closest("[hidden]") &&
      !element.parentElement?.closest("details:not([open])"),
    );
  const text = (element) => element.textContent.replace(/\s+/g, " ").trim();
  const restore = (modelContent) =>
    w.dispatchEvent(
      new w.CustomEvent("openai:set_globals", {
        detail: {
          globals: { widgetState: { modelContent, privateContent: {} } },
        },
      }),
    );
  const mode = (i) => one('[data-mode="' + i + '"]').click();
  const field = (id) => one('[data-field="' + id + '"] input[type=number]');
  const set = (input, value) => {
    input.value = value;
    input.dispatchEvent(new w.Event("change"));
  };
  const cautionText =
    "Seebeck data alone can leave several band parameters undetermined. Use independent measurements or hold parameters you know.";
  let count = 0;
  for (const n of [1, 2, 3])
    for (let mask = 0; mask < 2 ** n; mask++)
      for (let k = -1; k < n; k++)
        for (const mechanism of k < 0 ? ["ac", "dis", "ion", "mix"] : ["ac"])
          for (let selectedMode = 0; selectedMode < 3; selectedMode++) {
            const types = [0, 1, 2].map(
              (i) => ((mask >> i) & 1) + (i === k ? 2 : 0),
            );
            restore({ n, types, mechanism, selectedMode });
            const context = JSON.stringify({
              n,
              types,
              mechanism,
              selectedMode,
            });
            const caution = one("#sb-identifiability-caution");
            equal(
              visible(caution),
              n >= 2 && selectedMode === 0,
              "Parameters caution visibility " + context,
            );
            if (n >= 2 && selectedMode === 0) {
              equal(
                caution.closest(".params") !== null,
                true,
                "Caution belongs to Parameters",
              );
              equal(text(caution), cautionText, "Persistent caution copy");
            }
            const example = one("#sb-flat-profile-example");
            equal(
              visible(example),
              n === 3 && selectedMode === 0,
              "Illustrative example availability " + context,
            );
            equal(
              Boolean(example && example.open),
              false,
              "Mode selection does not opt into a result",
            );
            equal(
              visible(one("#sb-flat-profile-result")) &&
                Boolean(example && example.open),
              false,
              "Mode alone supplies no non-identifiability diagnosis",
            );
            count++;
          }
  equal(count, 270, "All allowed configurations checked");
  restore({ n: 3, types: [0, 1, 0], mechanism: "ac", selectedMode: 0 });
  set(field("ef"), "0.011");
  set(field("gap1"), "0.09");
  set(field("mass"), "2.8");
  one('[data-field="gap1"] .lock').click();
  one("#sb-bounds").click();
  const fieldState = () =>
    [...d.querySelectorAll(".field")].map((row) => ({
      id: row.dataset.field,
      inputs: [...row.querySelectorAll("input")].map((input) => [
        input.value,
        input.hidden,
        input.disabled,
      ]),
      lock: [
        row.querySelector(".lock").getAttribute("aria-pressed"),
        row.querySelector(".lock").disabled,
      ],
    }));
  const before = fieldState();
  equal(
    copy.parameters_caution.text,
    cautionText,
    "Caution matches canonical dictionary",
  );
  const example = one("#sb-flat-profile-example");
  // HTMLElement.click() does not implement details activation in jsdom.
  // Toggle the native disclosure there; Chrome also drives its summary below.
  example.open = true;
  example.dispatchEvent(new w.Event("toggle"));
  const result = one("#sb-flat-profile-result");
  equal(visible(result), true, "Opt-in example exposes illustrative Result");
  equal(
    result.dataset.resultCode,
    copy.status.id,
    "Result has canonical status code",
  );
  equal(
    result.dataset.issue,
    "band_composition_flat_profile",
    "Result has distinct flat-profile issue",
  );
  equal(
    text(result).includes(copy.status.label),
    true,
    "Result matches canonical status label",
  );
  equal(
    /illustrative/i.test(result.textContent),
    true,
    "Result identifies itself as illustrative",
  );
  equal(
    result.textContent.includes("Parameters not uniquely determined"),
    true,
    "Distinct parameter status label",
  );
  equal(
    /converged|\bconfident\b|\breliable parameters\b/i.test(result.textContent),
    false,
    "Result does not claim convergence or parameter confidence",
  );
  equal(
    /0(?:\.0+)?\s*(?:to|–|—|\.\.|…|−|-)\s*0\.02\s*eV/.test(result.textContent),
    true,
    "Illustrative EF interval is 0 to 0.02 eV",
  );
  equal(
    fieldState(),
    before,
    "Opening result preserves fields, bounds and locks",
  );
  example.open = false;
  example.open = true;
  equal(
    fieldState(),
    before,
    "Reopening result preserves fields, bounds and locks",
  );
  mode(1);
  equal(
    visible(one("#sb-identifiability-caution")),
    false,
    "Other modes hide caution",
  );
  equal(
    visible(one("#sb-flat-profile-example")),
    false,
    "Other modes hide example",
  );
  equal(
    one("#sb-flat-profile-example").open,
    false,
    "Mode switch closes example",
  );
  mode(0);
  equal(
    one("#sb-flat-profile-example").open,
    false,
    "Returning to S does not revive result",
  );
  equal(fieldState(), before, "Round trip preserves fields, bounds and locks");
  one("#sb-flat-profile-example").open = true;
  one('[data-page="guide"]').click();
  equal(
    one("#sb-flat-profile-example").open,
    false,
    "Leaving Fit closes example",
  );
  one('[data-page="fit"]').click();
  one("#sb-flat-profile-example").open = true;
  one("#sb-remove").click();
  equal(
    visible(one("#sb-flat-profile-example")),
    false,
    "Two bands hide example",
  );
  equal(
    one("#sb-flat-profile-example").open,
    false,
    "Removing band closes example",
  );

  const cueText =
    "With these band edges, every E_F inside the gap gives the same curves.";
  equal(
    copy.issues.find((issue) => issue.id === "band_composition_fermi_in_gap")
      .text,
    cueText,
    "In-gap cue matches canonical dictionary",
  );
  const cue = (expected, message) => {
    equal(visible(one("#sb-in-gap-note")), expected, message);
    if (expected)
      equal(text(one("#sb-in-gap-note")), cueText, "Conditional in-gap copy");
  };
  restore({ n: 3, types: [0, 1, 0], mechanism: "ac", selectedMode: 0 });
  set(field("ef"), "0.01");
  set(field("gap1"), "0.09");
  set(field("gap2"), "-0.02");
  cue(true, "Positive mixed band gap shows conditional cue");
  set(field("ef"), "0");
  cue(true, "Valence gap endpoint is included");
  set(field("ef"), "0.09");
  cue(true, "Conduction gap endpoint is included");
  set(field("ef"), "0.10");
  cue(false, "EF outside gap hides cue");
  set(field("ef"), "");
  cue(false, "Missing EF hides cue");
  set(field("ef"), "0.01");
  set(field("gap1"), "-0.01");
  cue(false, "Band overlap hides cue");
  set(field("gap1"), "");
  cue(false, "Missing band edge hides cue");
  restore({ n: 3, types: [0, 0, 0], mechanism: "ac", selectedMode: 0 });
  cue(false, "All conduction bands hide cue");
  restore({ n: 2, types: [0, 1, 0], mechanism: "ac", selectedMode: 0 });
  set(field("gap1"), "0.09");
  set(field("ef"), "0.01");
  cue(true, "Signed two-band Eg alias shows cue");
  one('[data-band="0"] [data-choice="CB"]').click();
  one('[data-band="1"] [data-choice="VB"]').click();
  set(field("gap1"), "0.09");
  set(field("ef"), "-0.01");
  cue(true, "Reversed signed edge alias retains physical gap cue");
  mode(1);
  cue(false, "Other fit modes hide conditional cue");
  return count;
}
// Item 10: literal N=8 examples distinguish single-valley and total DOS mass.
// Only rendered controls, visible results and the public host restore are used.
function verifyMassConvention(w) {
  const d = w.document;
  const one = (selector) => d.querySelector(selector);
  const text = (selector) =>
    one(selector)?.textContent.replace(/\s+/g, " ").trim();
  const equal = (actual, expected, message) => {
    if (actual !== expected)
      throw new Error(
        message + ": expected " + expected + ", received " + actual,
      );
  };
  const contains = (selector, expected) =>
    equal(
      text(selector)?.includes(expected),
      true,
      selector + " includes " + expected,
    );
  const restore = (modelContent, privateContent = {}) =>
    w.dispatchEvent(
      new w.CustomEvent("openai:set_globals", {
        detail: { globals: { widgetState: { modelContent, privateContent } } },
      }),
    );
  const set = (selector, value) => {
    const input = one(selector);
    input.value = value;
    input.dispatchEvent(new w.Event("change", { bubbles: true }));
  };
  let saved;
  w.openai = {
    setWidgetState: (snapshot) => {
      saved = JSON.parse(JSON.stringify(snapshot));
      return Promise.resolve();
    },
  };
  const mass = '[data-field="mass"] input[type=number]';
  const valleys = "#sb-valleys input";
  const output = "#sb-total-dos-mass";
  restore({ n: 2, types: [0, 1, 0], mechanism: "ac", selectedMode: 2 });
  contains('[data-field="mass"] label', "Single-valley DOS mass");
  set(valleys, "8");
  set(mass, "0.5");
  equal(one(output)?.hidden, false, "N=8 exposes derived total DOS mass");
  contains(output, "DOS mass (all equivalent valleys): 2 mₑ");
  set(mass, "2");
  contains(output, "DOS mass (all equivalent valleys): 8 mₑ");
  one('[data-field="mass"] .lock').click();
  one('[data-mode="0"]').click();
  contains(output, "8 mₑ");
  one('[data-mode="2"]').click();
  equal(
    one('[data-field="mass"] .lock').getAttribute("aria-pressed"),
    "true",
    "Held mass survives modes",
  );
  const snapshot = saved;
  restore({ n: 1, types: [0, 0, 0], mechanism: "ac", selectedMode: 0 });
  restore(snapshot.modelContent, snapshot.privateContent);
  contains(output, "8 mₑ");
  equal(one(mass).value, "2", "Restored editable mass is single-valley");
  equal(
    one('[data-field="mass"] .lock').getAttribute("aria-pressed"),
    "true",
    "Held mass survives restore",
  );
  set(valleys, "1");
  equal(one(output)?.hidden, true, "N=1 suppresses redundant total DOS mass");
  for (const invalid of ["0", "1.5", ""]) {
    set(valleys, invalid);
    equal(one(output)?.hidden, false, "Invalid N keeps diagnostic visible");
    contains(output, "—");
  }
  set(valleys, "8");
  for (const invalid of ["0", "-1", ""]) {
    set(mass, invalid);
    contains(output, "—");
  }
  set(mass, "0.5");
  contains(output, "2 mₑ");

  set(valleys, "6");
  set(mass, "0.209");
  const published = /: ([0-9.]+) mₑ/.exec(text(output));
  equal(
    Number(published?.[1]).toFixed(3),
    "0.690",
    "Jacquot Table I, p-Bi2Te3",
  );
  set(valleys, "8");
  set(mass, "0.5");

  const preview = one("#sb-p17-migration-preview");
  equal(Boolean(preview), true, "P17 migration example exists");
  preview.open = true;
  contains("#sb-p17-current-run", "Single-valley DOS mass");
  contains("#sb-p17-earlier-run", "DOS mass (all equivalent valleys)");
  contains("#sb-p17-earlier-run", "2 mₑ");
  contains("#sb-p17-earlier-run", "0.5 mₑ");
  contains("#sb-p17-earlier-run", "historical N = 8");
  equal(
    /Results/.test(text("#sb-p17-migration-preview")),
    true,
    "Results heading is explicit",
  );
  equal(
    /Earlier runs/.test(text("#sb-p17-migration-preview")),
    true,
    "Earlier runs heading is explicit",
  );
  equal(
    /÷|\//.test(text("#sb-p17-earlier-run")),
    true,
    "P17 conversion divides historical total DOS mass",
  );
  equal(
    /preserv|original|historical/i.test(text("#sb-p17-earlier-run")),
    true,
    "Earlier mass provenance is explicit",
  );
  const earlier = text("#sb-p17-earlier-run");
  set(valleys, "27");
  set(mass, "2");
  equal(
    text("#sb-p17-earlier-run"),
    earlier,
    "Earlier run uses immutable metadata, independent of editor N and mass",
  );
  one('[data-mode="1"]').click();
  equal(
    text("#sb-p17-earlier-run"),
    earlier,
    "Earlier metadata survives mode changes",
  );
}
function verifyFitReplay(w) {
  const assert = {
    equal(actual, expected) {
      if (actual !== expected)
        throw new Error(JSON.stringify({ actual, expected }));
    },
    deepEqual(actual, expected) {
      this.equal(JSON.stringify(actual), JSON.stringify(expected));
    },
    match(actual, expected) {
      if (!expected.test(actual))
        throw new Error(actual + " does not match " + expected);
    },
  };
  const d = w.document;
  const one = (s) => d.querySelector(s);
  const click = (id) => one("#sb-replay-" + id).click();
  const restore = (types, n = 3) =>
    w.dispatchEvent(
      new w.CustomEvent("openai:set_globals", {
        detail: {
          globals: {
            widgetState: {
              modelContent: { n, types, mechanism: "ac", selectedMode: 2 },
              privateContent: {},
            },
          },
        },
      }),
    );
  const edit = (id, value) => {
    const input = one('[data-field="' + id + '"] input[type=number]');
    input.value = value;
    input.dispatchEvent(new w.Event("change", { bubbles: true }));
  };
  const startValues = () =>
    ["gap1", "gap2"].map((id) => one('[data-field="' + id + '"] input')?.value);
  restore([0, 1, 0]);
  assert.equal(one("#sb-fit-replay").tagName, "DETAILS");
  assert.equal(one("#sb-fit-replay").open, false);
  one("#sb-fit-replay").open = true;
  edit("gap1", "0.1");
  edit("gap2", "0.04");
  const starts = startValues();
  assert.match(one("#sb-gap-origin").textContent, /CB₂ and VB₃/);
  assert.match(one("#sb-three-gap strong").title, /directness/);
  click("start");
  assert.equal(one("#sb-replay-status").textContent, "Fit…");
  assert.equal(one("#sb-three-gap .gap-fit-marker").textContent, "Fit…");
  assert.equal(one("#sb-gap-value").textContent, "0.06 eV");
  one("#sb-replay-next").focus();
  click("next");
  assert.equal(one("#sb-gap-value").textContent, "0.07 eV");
  assert.equal(d.activeElement.id, "sb-replay-next");
  assert.deepEqual(startValues(), starts);
  click("next");
  click("next");
  assert.equal(one("#sb-replay-status").textContent, "Fit…");
  assert.equal(one("#sb-replay-next").textContent, "Return final vector");
  assert.equal(one("#sb-gap-value").textContent, "0.06 eV");
  assert.match(one("#sb-gap-origin").textContent, /CB₂ and VB₃/);
  click("next");
  assert.equal(one("#sb-replay-status").textContent, "Complete");
  assert.equal(one("#sb-gap-value").textContent, "0.075 eV");
  assert.equal(one("#sb-three-gap .gap-fit-marker").textContent, "");
  assert.match(
    one("#sb-replay-result").textContent,
    /0.075 eV. Defined by CB₂ and VB₁/,
  );
  assert.deepEqual(startValues(), starts);
  // Cancel and failure discard preview offsets and restore researcher starts.
  for (const stop of ["cancel", "fail"]) {
    click("start");
    click("next");
    click(stop);
    click("next");
    assert.equal(
      one("#sb-replay-status").textContent,
      (stop === "cancel" ? "Cancelled" : "Failed") +
        " · starting values retained",
    );
    assert.equal(one("#sb-gap-value").textContent, "0.06 eV");
    assert.deepEqual(startValues(), starts);
    assert.equal(one("#sb-replay-result").textContent, "");
  }
  // Edits and rerenders invalidate a run; a stale replay cannot resume.
  click("start");
  click("next");
  edit("gap1", "0.2");
  click("next");
  assert.equal(one('[data-field="gap1"] input').value, "0.2");
  assert.match(one("#sb-replay-status").textContent, /^Cancelled/);
  click("start");
  one('[data-mode="1"]').click();
  assert.equal(
    one("#sb-replay-status").textContent,
    "Cancelled · model changed",
  );
  assert.equal(one("#sb-gap-value").textContent, "0.16 eV");
  // Held edges remain at their start value while previewing other edges.
  one('[data-field="gap1"] .lock').click();
  click("start");
  click("next");
  assert.equal(one("#sb-gap-value").textContent, "0.18 eV");
  assert.deepEqual(startValues(), ["0.2", "0.04"]);
  click("cancel");
  one("#sb-bounds").click();
  const low = one('[data-field="gap2"] .limits label:first-child input');
  low.value = "0.03";
  low.dispatchEvent(new w.Event("change", { bubbles: true }));
  click("start");
  click("next");
  assert.match(one("#sb-replay-status").textContent, /^Failed/);
  assert.equal(one("#sb-gap-value").textContent, "0.16 eV");
  assert.deepEqual(startValues(), ["0.2", "0.04"]);
  // Both two-band orientations show the computed value on the actual field,
  // alongside the fitting marker, while the editable start remains untouched.
  for (const types of [
    [0, 1, 0],
    [1, 0, 0],
  ]) {
    restore(types, 2);
    edit("gap1", "0.1");
    click("start");
    assert.equal(
      one('[data-field="gap1"] .gap-fit-marker').textContent,
      "Fit…",
    );
    assert.equal(
      one('[data-field="gap1"] .gap-current').textContent,
      "Current gap = 0.1 eV",
    );
    click("next");
    assert.equal(
      one('[data-field="gap1"] .gap-current').textContent,
      "Current gap = 0.09 eV",
    );
    assert.equal(one('[data-field="gap1"] input').value, "0.1");
    click("next");
    click("next");
    click("next");
    assert.equal(
      one('[data-field="gap1"] .gap-current').textContent,
      "Current gap = 0.075 eV",
    );
    assert.equal(one('[data-field="gap1"] input').value, "0.1");
    one("#sb-bounds").click();
    assert.equal(one('[data-field="gap1"] .gap-current'), null);
    assert.equal(one('[data-field="gap1"] input').value, "0.1");
    click("start");
    click("next");
    one('[data-mode="1"]').click();
    assert.equal(one('[data-field="gap1"] .gap-current'), null);
    assert.equal(one('[data-field="gap1"] input').value, "0.1");
    assert.equal(
      one("#sb-replay-status").textContent,
      "Cancelled · model changed",
    );
  }
  assert.equal(d.querySelector("input[aria-describedby]"), null);
  const help = one('[data-field="gap1"] .help');
  help.click();
  assert.equal(one('[data-field="gap1"] .field-caption').hidden, false);
  help.click();
  assert.equal(one('[data-field="gap1"] .field-caption').hidden, true);
  restore([1, 1, 1]);
  click("start");
  click("next");
  assert.equal(one("#sb-replay-gap").hidden, true);
  assert.equal(one("#sb-replay-gap").textContent, "");
  assert.equal(
    d.querySelector(
      "output, [aria-live], [role=status], [role=alert], .sr-only",
    ),
    null,
  );
}
// Item 12: public notation, holds and integer valley validation through real controls.
function verifyParameterNotation(w) {
  const d = w.document;
  const one = (s) => d.querySelector(s);
  const field = (id, s) => one('[data-field="' + id + '"] ' + s);
  const equal = (a, b, message) => {
    if (a !== b)
      throw new Error(message + ": expected " + b + ", received " + a);
  };
  const restore = (modelContent, privateContent = {}) =>
    w.dispatchEvent(
      new w.CustomEvent("openai:set_globals", {
        detail: { globals: { widgetState: { modelContent, privateContent } } },
      }),
    );
  const set = (input, value) => {
    input.value = value;
    input.dispatchEvent(new w.Event("change", { bubbles: true }));
  };
  let saved;
  w.openai = {
    setWidgetState: (s) => {
      saved = JSON.parse(JSON.stringify(s));
      return Promise.resolve();
    },
  };
  for (const [mechanism, kind, unit] of [
    ["ac", "acPh", "scale: S/m"],
    ["dis", "dis", "scale: S/(m·K)"],
    ["ion", "ii", "S/m"],
    ["mix", "acPh", "scale: S/m"],
  ]) {
    for (const n of [1, 2, 3])
      for (const selectedMode of [0, 1, 2]) {
        restore({ n, types: [0, 1, 0], mechanism, selectedMode });
        if (selectedMode) {
          equal(
            field("scale", "label").textContent,
            "τ" +
              kind +
              ",1" +
              (mechanism !== "ion" && n > 1 && selectedMode === 1
                ? " / mb,1"
                : ""),
            "absolute notation",
          );
          equal(
            field("scale", ".unit").textContent,
            unit,
            "coefficient SI units",
          );
          if (n > 1)
            equal(
              field("ratio" + (n - 1), "label").textContent,
              "τ" + kind + "," + n + " / τ" + kind + ",1",
              "relative band indices",
            );
        }
        if (mechanism === "mix" && (n > 1 || selectedMode))
          equal(
            field("mix" + (n - 1), "label").textContent,
            "τacPh," + n + " / τdis," + n,
            "mixed ratio",
          );
        for (const input of d.querySelectorAll("#sb-valleys input")) {
          set(input, "1.5");
          equal(
            input.validationMessage,
            "Enter a positive integer valley count.",
            "fractional edit diagnostic",
          );
          one("#sb-replay-start").click();
          equal(
            one("#sb-replay-status").textContent,
            "Cannot replay · enter a positive integer valley count.",
            "fractional replay rejected",
          );
          set(input, "2");
          equal(input.checkValidity(), true, "valid integer recovers");
        }
      }
  }
  restore({ n: 2, types: [0, 1, 0], mechanism: "ion", selectedMode: 2 });
  field("scale", ".lock").click();
  equal(
    field("scale", ".lock").textContent.endsWith("Held"),
    true,
    "researcher hold caption",
  );
  equal(
    field("scale", ".lock").dataset.tooltip.includes("researcher"),
    true,
    "researcher hold reason",
  );
  one('[data-mode="0"]').click();
  equal(
    field("mass", ".lock").textContent.endsWith("Held"),
    true,
    "mode hold caption",
  );
  equal(field("mass", ".lock").disabled, true, "mode hold cannot be toggled");
  one('[data-mode="2"]').click();
  equal(
    field("scale", ".lock").getAttribute("aria-pressed"),
    "true",
    "hold survives mode",
  );
  const snapshot = saved;
  restore(snapshot.modelContent, snapshot.privateContent);
  equal(
    field("scale", ".lock").textContent.endsWith("Held"),
    true,
    "hold survives restore",
  );
  for (const imported of ["1.5", "0", "-2", "", "9007199254740993"]) {
    restore(
      { n: 2, types: [0, 1, 0], mechanism: "ac", selectedMode: 2 },
      { values: { N0: imported } },
    );
    const input = one("#sb-valleys input");
    equal(input.value, imported, "import preserved without rounding");
    equal(
      input.validationMessage,
      "Enter a positive integer valley count.",
      "import diagnostic",
    );
    one("#sb-replay-start").click();
    equal(
      one("#sb-replay-status").textContent,
      "Cannot replay · enter a positive integer valley count.",
      "invalid import rejected",
    );
    one('[data-mode="1"]').click();
    equal(
      one("#sb-valleys input").value,
      imported,
      "mode preserves invalid historical value",
    );
    restore(saved.modelContent, saved.privateContent);
    equal(
      one("#sb-valleys input").value,
      imported,
      "save/restore preserves historical value",
    );
    set(one("#sb-valleys input"), "3");
    one("#sb-replay-start").click();
    equal(
      one("#sb-replay-status").textContent,
      "Fit…",
      "corrected integer allows replay",
    );
    one("#sb-replay-cancel").click();
  }
  restore({ n: 1, types: [0, 1, 0], mechanism: "ac", selectedMode: 2 });
  set(one("#sb-valleys input"), "8");
  set(one("#sb-valleys input"), "2.5");
  one('[data-mode="1"]').click();
  equal(
    one("#sb-valleys input").value,
    "8",
    "invalid edit does not replace saved integer",
  );
  restore({ n: 2, types: [2, 1, 0], mechanism: "ac", selectedMode: 2 });
  equal(
    field("amplitude0", "label").textContent,
    "(Cl/Edef²)1",
    "Kane physical input retained",
  );
  equal(
    field("amplitude0", ".unit").textContent,
    "Pa/eV²",
    "Kane units retained",
  );
}
const parameterLabels = Object.fromEntries(
  labels.fields.map((entry) => [entry.key, entry]),
);
for (const [key, label, unit] of [
  ["amp", "τ_acPh,1", "S/m"],
  ["alloy_amp", "τ_dis,1", "S/(m·K)"],
  ["ionized_amp", "τ_ii,1", "S/m"],
  ["ionized_relative", "τ_ii,i/τ_ii,1", "1"],
  ["mixed_ratio", "τ_acPh,i/τ_dis,i", "1"],
]) {
  assert.equal(parameterLabels[key].label_en, label, key + " schema label");
  assert.equal(parameterLabels[key].display_unit, unit, key + " schema units");
}
verifyParameterNotation(w);
console.log(
  "Item 12: channel notation, SI units, holds, integer N and imported-value replay rejection passed.",
);
verifyFitReplay(w);
console.log(
  "Item 11: isolated accepted snapshots, switched final defining pair, cancellation/failure, holds/bounds, same polarity and keyboard focus passed.",
);
verifyMassConvention(w);
console.log(
  "Item 10: derived DOS mass, Jacquot Table I (p-Bi2Te3), invalid inputs, held/restored state and immutable P17 earlier-run example passed.",
);
verifyIdentifiability(w, labels.identifiability);
console.log(
  "Item 9: 270 caution states, opt-in Result, in-gap cues and stable parameter state passed.",
);
verifyBandTransitions(w);
console.log("Signed gaps and item 8 DOM state transitions passed.");
console.log(
  checks +
    " matrix states match JSON. Lock, editable manual value, hidden bounds, tooltips and restore passed.",
);
if (process.argv[2] || process.env.FIT_GUIDE_CHROME === "1") {
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
      if (process.argv[2])
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
      await page.evaluate("(" + verifyBandTransitions.toString() + ")(window)");
      await page.evaluate("(" + verifyFitReplay.toString() + ")(window)");
      await page.evaluate(() =>
        globalThis.dispatchEvent(
          new globalThis.CustomEvent("openai:set_globals", {
            detail: {
              globals: {
                widgetState: {
                  modelContent: {
                    n: 3,
                    types: [0, 1, 0],
                    mechanism: "ac",
                    selectedMode: 2,
                  },
                  privateContent: {},
                },
              },
            },
          }),
        ),
      );
      await page.locator("#sb-p-gap1").fill("0.1");
      await page.locator("#sb-p-gap2").fill("0.04");
      await page.locator("#sb-p-gap2").press("Tab");
      const replaySummary = page.locator("#sb-fit-replay > summary");
      if (await page.locator("#sb-fit-replay").evaluate((el) => el.open))
        await replaySummary.press("Enter");
      await replaySummary.focus();
      await replaySummary.press("Enter");
      await replaySummary.press("Tab");
      assert.equal(
        await page.evaluate(() => globalThis.document.activeElement.id),
        "sb-replay-start",
      );
      await page.keyboard.press("Enter");
      await page.keyboard.press("Tab");
      assert.equal(
        await page.evaluate(() => globalThis.document.activeElement.id),
        "sb-replay-next",
      );
      await page.keyboard.press("Enter");
      assert.equal(
        await page.locator("#sb-gap-value").textContent(),
        "0.07 eV",
      );
      assert.equal(
        await page.evaluate(() => globalThis.document.activeElement.id),
        "sb-replay-next",
      );
      await page.keyboard.press("Tab");
      assert.equal(
        await page.evaluate(() => globalThis.document.activeElement.id),
        "sb-replay-cancel",
      );
      await page.keyboard.press("Enter");
      assert.equal(
        await page.locator("#sb-gap-value").textContent(),
        "0.06 eV",
      );
      assert.ok(
        await page.evaluate(
          () => globalThis.document.documentElement.scrollWidth <= 320,
        ),
        "expanded offline replay fits mobile viewport",
      );
      console.log(
        "Chrome item 11: native disclosure/Tab/Enter, isolated replay, final vector, rerender and mobile layout passed.",
      );
      await page.evaluate(
        "(" + verifyParameterNotation.toString() + ")(window)",
      );
      console.log(
        "Chrome item 12: mechanism notation, holds, integer N and imported-value replay rejection passed.",
      );
      await page.evaluate("(" + verifyMassConvention.toString() + ")(window)");
      await page.locator("#sb-valleys input").first().fill("8");
      await page.locator("#sb-p-mass").fill("0.5");
      await page.locator("#sb-p-mass").press("Tab");
      assert.match(
        await page.locator("#sb-total-dos-mass").innerText(),
        /: 2 mₑ/,
      );
      await page.locator("#sb-p17-migration-preview").evaluate((el) => {
        el.open = false;
      });
      await page.locator("#sb-p17-migration-preview > summary").focus();
      await page.locator("#sb-p17-migration-preview > summary").press("Enter");
      await page.locator("#sb-p17-earlier-run").waitFor({ state: "visible" });
      assert.ok(
        await page.evaluate(
          () => globalThis.document.documentElement.scrollWidth <= 320,
        ),
        "expanded P17 mass example fits mobile viewport",
      );
      console.log(
        "Chrome item 10: mass conventions, native editing and immutable earlier-run metadata passed.",
      );
      await page.evaluate(
        "(" +
          verifyIdentifiability.toString() +
          ")(window," +
          JSON.stringify(labels.identifiability) +
          ")",
      );
      await page.evaluate(() =>
        globalThis.dispatchEvent(
          new globalThis.CustomEvent("openai:set_globals", {
            detail: {
              globals: {
                widgetState: {
                  modelContent: {
                    n: 3,
                    types: [0, 1, 0],
                    mechanism: "ac",
                    selectedMode: 0,
                  },
                  privateContent: {},
                },
              },
            },
          }),
        ),
      );
      const summary = page.locator("#sb-flat-profile-example > summary");
      await summary.focus();
      await summary.press("Enter");
      assert.equal(
        await page
          .locator("#sb-flat-profile-example")
          .evaluate((el) => el.open),
        true,
      );
      await page
        .locator("#sb-flat-profile-result")
        .waitFor({ state: "visible" });
      assert.ok(
        await page.evaluate(
          () => globalThis.document.documentElement.scrollWidth <= 320,
        ),
        "expanded flat-profile result fits mobile viewport",
      );
      await page.locator('[data-mode="1"]').click();
      await page
        .locator("#sb-flat-profile-result")
        .waitFor({ state: "hidden" });
      console.log(
        "Chrome item 9: 270 caution states and native opt-in Result disclosure passed.",
      );
      console.log(
        "Chrome item 8 DOM transitions and 960/320 px layout passed.",
      );
    } finally {
      await browser.close();
    }
  })().catch((e) => {
    console.error(e.message);
    process.exitCode = 1;
  });
}
