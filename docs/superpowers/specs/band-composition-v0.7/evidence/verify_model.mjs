import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
const loadPackage = createRequire(
  new URL("../../../../../apps/web/package.json", import.meta.url),
);
const { JSDOM } = loadPackage("jsdom");
const html = fs.readFileSync(
  path.join(import.meta.dirname, "legacy-model.html"),
  "utf8",
);
const options = { runScripts: "dangerously", url: "http://seeband.test/" };
const dom = new JSDOM(html, options);
const d = dom.window.document,
  q = (s) => d.querySelector(s);
const label = () => q("[data-name]").textContent;
const shape = (i, v) => q('[data-i="' + i + '"][data-v="' + v + '"]');
const scatter = q("[data-scattering]");
function choose(v) {
  scatter.value = v;
  scatter.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
}
assert.equal(label(), "3 SPB");
assert.equal(q("[data-add]").hidden, true);
assert.deepEqual(
  Array.from(
    d.querySelectorAll('[data-key="type"][aria-pressed="true"]'),
    (x) => x.dataset.v,
  ),
  ["VB", "CB", "VB"],
);
q("[data-remove]").click();
assert.equal(label(), "DPB");
shape(1, "Kane").click();
assert.equal(label(), "1 SKB + 1 SPB");
assert.equal(shape(0, "Kane").disabled, true);
assert.deepEqual(
  Array.from(scatter.options)
    .filter((o) => !o.disabled)
    .map((o) => o.value),
  ["acPh"],
);
q("[data-add]").click();
assert.equal(label(), "1 SKB + 2 SPB");
assert.equal(shape(2, "Kane").disabled, true);
shape(1, "Parabolic").click();
for (const count of [3, 2, 1]) {
  assert.equal(d.querySelectorAll("[data-n]").length, count);
  for (const v of ["acPh", "dis", "ionized", "acPhDis"]) {
    assert.equal(
      Array.from(scatter.options).filter((x) => !x.disabled).length,
      4,
    );
    choose(v);
    assert.equal(shape(0, "Kane").disabled, v !== "acPh");
  }
  choose("acPh");
  shape(0, "Kane").click();
  if (count === 1) assert.equal(label(), "SKB");
  shape(0, "Parabolic").click();
  if (count > 1) q("[data-remove]").click();
  else assert.equal(q("[data-remove]").hidden, true);
}
// Even the archived Model-only fixture rejects pasted and restored fractional counts.
const count = () => q('[data-n="0"]');
const edit = (field, value) => {
  field.value = value;
  field.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  field.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
};
const key = "seeband.model-review.v1";
const snapshot = () => JSON.parse(dom.window.localStorage.getItem(key));
edit(count(), "2");
for (const raw of ["1.1", "1,1"]) {
  edit(count(), raw);
  assert.equal(count().value, "");
  assert.equal(snapshot().bands[0].n, null);
}
const invalid = { ...snapshot(), bands: [{ ...snapshot().bands[0], n: 1.1 }] };
const reopened = new JSDOM(html, {
  ...options,
  beforeParse(w) {
    w.localStorage.setItem(key, JSON.stringify(invalid));
  },
});
assert.equal(reopened.window.document.querySelector("[data-n]").value, "");
reopened.window.close();
count().focus();
edit(count(), "6");
assert.equal(snapshot().bands[0].n, 6);
edit(q("[data-temp=low]"), "51.25");
assert.equal(q("[data-temp=low]").value, "51,25");
assert.equal(snapshot().low, 51.25);
console.log(
  "PASS: VB/CB/VB 3 SPB, DPB, 1 SKB + 1 SPB, 1 SKB + 2 SPB, SKB, SPB; 1–3 degeneracy fields; single Kane and global acPh constraint. Model mock only.",
);
