// Exercise the public editor and its rendered controls. Expected eligibility comes
// from the scope: three bands are parabolic only; supported Kane models require acoustic scattering.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const requireWeb = createRequire(
  new URL("../../../../../apps/web/package.json", import.meta.url),
);
const { chromium } = requireWeb("@playwright/test");
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const url = process.env.FIT_GUIDE_FILE
    ? pathToFileURL(process.env.FIT_GUIDE_FILE)
    : new URL("../fit-guide.html", import.meta.url);
  await page.goto(url.href);
  const rows = await page.evaluate(() => {
    const { fitGuide, document, localStorage } = globalThis;
    const scatter = document.querySelector("#sb-scatter");
    const rows = [];
    for (const n of [1, 2, 3]) {
      for (let mask = 0; mask < 2 ** n; mask++) {
        for (let kane = -1; kane < n; kane++) {
          const types = [0, 1, 2].map(
            (i) => ((mask >> i) & 1) + (i === kane ? 2 : 0),
          );
          const bands = types
            .slice(0, n)
            .map(
              (t) => ["VB Parabolic", "CB Parabolic", "VB Kane", "CB Kane"][t],
            );
          for (const selectedMode of [0, 1, 2]) {
            // The acoustic positive control sets the same bands and mode before each group of refusals.
            for (const [mechanism, label] of [
              ["ac", "acPh"],
              ["dis", "dis"],
              ["ion", "ii"],
              ["mix", "acPh+dis"],
            ]) {
              const row = {
                bands,
                mode: ["S", "S+rho", "S+rho+Hall"][selectedMode],
                scattering: label,
              };
              const check = (ok, reason) => {
                if (!ok) throw new Error(JSON.stringify(row) + ": " + reason);
              };
              const unsupported = n === 3 && kane >= 0;
              const incompatible = kane >= 0 && mechanism !== "ac";
              const rejected = unsupported || incompatible;
              const state = () => JSON.stringify(fitGuide.snapshot());
              const saved = () => localStorage.getItem(fitGuide.storageKey);
              const before = state(),
                draft = saved();
              const modelContent = { n, types, mechanism, selectedMode };
              const bandIds = Array.from({ length: n }, (_, i) => i + 1);
              const problem = fitGuide.restore({
                modelContent,
                privateContent: {
                  stateVersion: 4,
                  bandIds,
                  values: {
                    ef: rejected ? "0.031" : "0.013",
                    ...Object.fromEntries(
                      bandIds.map((id) => ["band/" + id + "/valleys", "2"]),
                    ),
                  },
                  held: rejected ? [] : ["ef"],
                  limits: rejected ? {} : { ef: ["-0.12", "0.24"] },
                },
              });
              if (rejected) {
                check(
                  problem?.code ===
                    (unsupported
                      ? "unsupported_composition"
                      : "incompatible_scattering") &&
                    problem.path ===
                      (unsupported
                        ? "modelContent.types"
                        : "modelContent.mechanism"),
                  "expected explicit refusal with composition precedence",
                );
                const notice = document.querySelector(
                  "#sb-compatibility-error",
                );
                check(
                  notice?.checkVisibility() &&
                    notice.textContent.includes(problem.message) &&
                    (unsupported
                      ? /three.band/i.test(problem.message) &&
                        /parabolic/i.test(problem.message)
                      : /Kane/i.test(problem.message) &&
                        /acoustic/i.test(problem.message)),
                  "missing visible reason",
                );
                check(
                  state() === before && saved() === draft,
                  "invalid restore changed the editor or saved draft",
                );
                if (!unsupported) {
                  check(
                    scatter.disabled && scatter.value === "ac",
                    "forbidden scattering selectable",
                  );
                  scatter.value = mechanism;
                  scatter.dispatchEvent(
                    new globalThis.Event("change", { bubbles: true }),
                  );
                  check(
                    scatter.value === "ac" &&
                      state() === before &&
                      saved() === draft,
                    "forced scattering change escaped the guard",
                  );
                }
              } else {
                check(!problem, "compatible restore refused");
                const snapshot = fitGuide.snapshot();
                const active = snapshot.modelContent;
                check(
                  snapshot.privateContent.held.includes("ef") &&
                    snapshot.privateContent.values.ef === "0.013" &&
                    snapshot.privateContent.limits.ef.join(",") ===
                      "-0.12,0.24",
                  "positive control lost its custom Fermi energy, bounds or hold",
                );
                check(
                  active.n === n &&
                    active.selectedMode === selectedMode &&
                    JSON.stringify(active.types.slice(0, n)) ===
                      JSON.stringify(types.slice(0, n)) &&
                    active.mechanism === mechanism,
                  "restore changed valid inputs",
                );
                check(
                  scatter.value === mechanism && scatter.disabled === kane >= 0,
                  "rendered scattering mismatch",
                );
                check(
                  document
                    .querySelector('[data-mode="' + selectedMode + '"]')
                    .getAttribute("aria-pressed") === "true",
                  "rendered fit mode mismatch",
                );
                for (let i = 0; i < n; i++) {
                  const band = document.querySelector(
                    '[data-band="' + i + '"]',
                  );
                  const selected = [
                    ...band.querySelectorAll(
                      '[data-choice][aria-pressed="true"]',
                    ),
                  ].map((b) => b.dataset.choice);
                  check(
                    selected.join(" ") === bands[i],
                    "rendered band mismatch",
                  );
                  if (mechanism !== "ac")
                    check(
                      band.querySelector('[data-choice="Kane"]').disabled,
                      "Kane selectable with nonacoustic scattering",
                    );
                }
              }
              rows.push({
                ...row,
                outcome: rejected ? problem.code : "accepted",
              });
            }
          }
        }
      }
    }
    return rows;
  });
  const keys = rows.map((r) => JSON.stringify([r.bands, r.mode, r.scattering]));
  assert.equal(new Set(keys).size, 576);
  assert.equal(rows.length, 576);
  for (const [i, invalid] of [18, 72, 0].entries()) {
    const group = rows.filter((r) => r.bands.length === i + 1);
    assert.equal(
      group.filter((r) => r.outcome === "incompatible_scattering").length,
      invalid,
    );
    assert.equal(
      group.filter((r) => r.outcome === "accepted").length,
      [30, 72, 96][i],
    );
  }
  assert.equal(rows.filter((r) => r.outcome === "accepted").length, 198);
  assert.equal(
    rows.filter((r) => r.outcome === "incompatible_scattering").length,
    90,
  );
  assert.equal(
    rows.filter((r) => r.outcome === "unsupported_composition").length,
    288,
  );

  // Exercise both UI edit directions, including forced events on disabled controls.
  await page.evaluate(() => {
    const { fitGuide, document, localStorage } = globalThis;
    for (const modelContent of [
      { n: 2, types: [2, 1, 0], mechanism: "ac", selectedMode: 1 },
      { n: 3, types: [0, 1, 0], mechanism: "ac", selectedMode: 2 },
    ]) {
      if (fitGuide.restore({ modelContent, privateContent: {} }))
        throw new Error("UI control setup refused");
      const before = JSON.stringify(fitGuide.snapshot());
      const draft = localStorage.getItem(fitGuide.storageKey);
      const controls =
        modelContent.n === 2
          ? [document.querySelector("#sb-add")]
          : [...document.querySelectorAll('[data-choice="Kane"]')];
      if (controls.length !== (modelContent.n === 2 ? 1 : 3))
        throw new Error("missing UI guards");
      for (const control of controls) {
        if (!control.disabled)
          throw new Error("unsupported composition selectable");
        control.dispatchEvent(
          new globalThis.MouseEvent("click", { bubbles: true }),
        );
        if (
          JSON.stringify(fitGuide.snapshot()) !== before ||
          localStorage.getItem(fitGuide.storageKey) !== draft
        )
          throw new Error("forced edit changed editor or saved draft");
      }
    }
  });

  for (const modelContent of [
    { n: 2, types: [1, 2, 0], mechanism: "ion", selectedMode: 2 },
    { n: 3, types: [1, 2, 0], mechanism: "ion", selectedMode: 2 },
  ]) {
    const badDraft = JSON.stringify({
      modelContent,
      privateContent: {},
    });
    await page.evaluate(
      (s) => globalThis.localStorage.setItem(globalThis.fitGuide.storageKey, s),
      badDraft,
    );
    await page.reload();
    assert.equal(
      await page.locator("#sb-compatibility-error").isVisible(),
      true,
    );
    assert.match(
      await page.locator("#sb-compatibility-error").innerText(),
      modelContent.n === 3 ? /three.band/i : /Kane/i,
    );
    assert.equal(
      await page.evaluate(() =>
        globalThis.localStorage.getItem(globalThis.fitGuide.storageKey),
      ),
      badDraft,
    );
    assert.equal(await page.locator("#sb-add").isHidden(), true);
    await page.locator('[data-page="guide"]').click();
    await page.locator('[data-page="fit"]').click();
    await page.locator("#sb-bounds").click();
    assert.equal(
      await page.evaluate(() =>
        globalThis.localStorage.getItem(globalThis.fitGuide.storageKey),
      ),
      badDraft,
    );
    assert.equal(
      await page.locator("#sb-compatibility-error").isVisible(),
      true,
    );
    await page.locator("#sb-remove").click();
    assert.equal(
      await page.evaluate(
        () =>
          JSON.parse(
            globalThis.localStorage.getItem(globalThis.fitGuide.storageKey),
          ).modelContent.n,
      ),
      2,
    );
  }
  if (process.argv.includes("--cases")) {
    for (const row of rows) console.log(JSON.stringify(row));
  } else {
    console.log(
      "Chromium Fit/Guide: 576 distinct ordered requests; 198 accepted, 378 explicitly rejected.",
    );
    console.log(
      "Bands     Accepted    Invalid scattering    Unsupported composition",
    );
    for (const n of [1, 2, 3]) {
      const group = rows.filter((r) => r.bands.length === n);
      console.log(
        [
          n,
          group.filter((r) => r.outcome === "accepted").length,
          group.filter((r) => r.outcome === "incompatible_scattering").length,
          group.filter((r) => r.outcome === "unsupported_composition").length,
        ].join("         "),
      );
    }
    console.log(
      "90 incompatible_scattering refusals at modelContent.mechanism; 288 unsupported_composition refusals at modelContent.types, before scattering validation. All refusals show a visible reason and preserve editor and stored draft; forced scattering changes blocked.",
    );
    console.log(
      "Both UI edit directions blocked unsupported composition, including forced clicks. Invalid scattering and unsupported-composition drafts survived reload and navigation until a deliberate edit.",
    );
  }
} finally {
  await browser.close();
}
