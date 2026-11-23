// Reference for the hold decision *after* source checksum and identity validation.
// The fixtures use the eligible Fermi and acoustic scale rows of legacy acoustic DPB.
import assert from "node:assert/strict";
const ef = "ef";
const acoustic = "band/1/scale/ac:S/m";
const eligibility = {
  dpb_s: { fermi_energy: ef },
  dpb_s_rho: { fermi_energy: ef, A: acoustic },
  dpb_s_rho_rh: { fermi_energy: ef, A: acoustic },
};

function migrateHolds(content, eligible) {
  const votes = new Map();
  const modes = new Set([
    ...Object.keys(content.held),
    ...Object.keys(content.parameters ?? {}),
    ...Object.keys(content.guessedParameters ?? {}),
    ...Object.keys(content.customBounds ?? {}),
    content.selection.fitMode,
  ]);
  for (const mode of modes) {
    const names = content.held[mode] ?? [];
    for (const [name, identity] of Object.entries(eligible[mode] ?? {})) {
      if (!votes.has(identity)) votes.set(identity, new Map());
      votes.get(identity).set(mode, names.includes(name));
    }
  }
  const holds = {},
    conflicts = {};
  for (const [identity, byMode] of votes) {
    if (byMode.has(content.selection.fitMode)) {
      holds[identity] = byMode.get(content.selection.fitMode);
    } else if (new Set(byMode.values()).size === 1) {
      holds[identity] = byMode.values().next().value;
    } else {
      conflicts[identity] = Object.fromEntries(byMode);
    }
  }
  return { holds, conflicts };
}
for (const version of [1, 2]) {
  const content = {
    selection: { model: "dpb", scattering: "acPh", fitMode: "dpb_s" },
    held: {
      dpb_s: ["fermi_energy", "unmapped"],
      dpb_s_rho: ["A"],
      dpb_s_rho_rh: [],
    },
    fit: { request: null, result: { held: ["fermi_energy"] } },
  };
  if (version === 2) content.selection.parameterization = "explicit_fermi_v1";
  const original = JSON.stringify(content);
  const migrated = migrateHolds(content, eligibility);
  assert.deepEqual(migrated.holds, { [ef]: true });
  assert.deepEqual(migrated.conflicts, {
    [acoustic]: { dpb_s_rho: true, dpb_s_rho_rh: false },
  });
  assert.equal(JSON.stringify(content), original);
  const selected = {
    ...content,
    selection: { ...content.selection, fitMode: "dpb_s_rho_rh" },
  };
  assert.deepEqual(migrateHolds(selected, eligibility), {
    holds: { [ef]: false, [acoustic]: false },
    conflicts: {},
  });
  const agree = { ...content, held: { ...content.held, dpb_s_rho_rh: ["A"] } };
  assert.equal(migrateHolds(agree, eligibility).holds[acoustic], true);
  assert.deepEqual(migrateHolds({ ...content, held: {} }, eligibility), {
    holds: { [ef]: false },
    conflicts: {},
  });
  const untouched = { ...selected, held: { dpb_s_rho: ["A", "fermi_energy"] } };
  assert.deepEqual(migrateHolds(untouched, eligibility), {
    holds: { [ef]: false, [acoustic]: false },
    conflicts: {},
  });
  const visited = {
    ...content,
    held: { dpb_s_rho: ["A"] },
    customBounds: { dpb_s_rho_rh: { A: [1, 100] } },
  };
  assert.deepEqual(migrateHolds(visited, eligibility).conflicts, {
    [acoustic]: { dpb_s_rho: true, dpb_s_rho_rh: false },
  });
  assert.deepEqual(JSON.parse(JSON.stringify(migrated)), migrated);
}
console.log(
  "v1/v2 eligible hold decisions passed: active choice, inactive disagreement, consensus, missing modes, unknown field preservation and unchanged source.",
);
