import { apiClient, type ParseRequest } from "@/api/client";
import { failureMessage } from "@/data/messages";
import { readFileText } from "@/data/readFile";
import { columnOf, requestMapping, unitDoubts, type Unit } from "@/data/units";
import {
  firstRowOf,
  loadedAs,
  QUANTITIES,
  useSessionStore,
  type ColumnRole,
  type ParsedTable,
  type Quantity,
  type SessionData,
} from "@/session/store";

// Stops the request itself, so that a cancelled or replaced read uses nothing more on the server.
let current: AbortController | null = null;

function stopCurrentRequest(): AbortSignal {
  current?.abort();
  current = new AbortController();
  return current.signal;
}

function store() {
  return useSessionStore.getState();
}

function clearData() {
  for (const quantity of QUANTITIES) {
    store().removeData(quantity);
  }
}

/** The column and unit a quantity was read from, which a confirmation of its values is about. */
function readFrom(entry: SessionData, quantity: Quantity) {
  const role = loadedAs(quantity, entry);
  return entry.readAs?.find((item) => item.role === role);
}

/**
 * Whether the user confirmed these very values before a re-read of the same table, as when only
 * another column changed. New values, or the same read from another column or unit, need a new
 * confirmation.
 */
function stillConfirmed(
  before: SessionData | undefined,
  after: SessionData,
  quantity: Quantity,
): boolean {
  if (before?.unitConfirmed !== true || before.text !== after.text) {
    return false;
  }
  const [was, is] = [readFrom(before, quantity), readFrom(after, quantity)];
  const same = (a: readonly number[], b: readonly number[]) =>
    a.length === b.length && a.every((value, index) => value === b[index]);
  return (
    was?.column === is?.column &&
    was?.unit === is?.unit &&
    loadedAs(quantity, before) === loadedAs(quantity, after) &&
    same(before.measurement.values, after.measurement.values) &&
    same(before.measurement.temperature_k, after.measurement.temperature_k)
  );
}

function applyTable(
  name: string,
  text: string,
  table: ParsedTable,
  before: Partial<Record<Quantity, SessionData>> = {},
) {
  for (const quantity of QUANTITIES) {
    const measurement = table.measurements[quantity];
    if (measurement === undefined) {
      store().removeData(quantity);
    } else {
      const entry: SessionData = {
        measurement,
        source: { kind: "file", name },
        extrapolated: false,
        text,
        readAs: table.mapping,
        unitDoubts: unitDoubts(
          table.warnings,
          columnOf(table.mapping, loadedAs(quantity, { measurement })),
        ),
        firstRow: firstRowOf(table),
      };
      store().setData(quantity, {
        ...entry,
        unitConfirmed: stillConfirmed(before[quantity], entry, quantity)
          ? true
          : undefined,
      });
    }
  }
}

/**
 * Reads a table, or reads it again with a user's mapping, as the API keeps nothing between calls.
 *
 * The state is in the store, so it stays across screens, and the last request is the one that
 * counts. Old data go first, as a fit from them would not match what the screen shows.
 */
async function read(
  name: string,
  text: string,
  mapping: ColumnRole[] | null,
  table: ParsedTable | null,
) {
  const request = store().startSingleFile({
    name,
    text,
    mapping: mapping ?? [],
    table,
  });
  // A change of one column keeps what the user confirmed about the others, if they read the same.
  const before = mapping === null ? {} : { ...store().data };
  clearData();
  const signal = stopCurrentRequest();
  const body: ParseRequest = mapping === null ? { text } : { text, mapping };
  try {
    const parsed = await apiClient.postParse(body, signal);
    if (store().singleFile?.request === request) {
      store().finishSingleFile(parsed);
      applyTable(name, text, parsed, before);
    }
  } catch (error) {
    if (store().singleFile?.request === request) {
      store().failSingleFile(failureMessage(error));
    }
  }
}

export async function loadSingleFile(file: File) {
  // This takes the place of anything before it now, so that a read of a slow file cannot come back
  // after a removal, a change of source or a newer file.
  const request = store().startSingleFile({
    name: file.name,
    text: "",
    mapping: [],
    table: null,
  });
  clearData();
  let text: string;
  try {
    text = await readFileText(file);
  } catch (error) {
    if (store().singleFile?.request === request) {
      store().failSingleFile(failureMessage(error));
    }
    return;
  }
  if (store().singleFile?.request === request) {
    await read(file.name, text, null, null);
  }
}

export function failSingleFile(message: string) {
  clearData();
  store().startSingleFile({ name: "", text: "", mapping: [], table: null });
  store().failSingleFile(message);
}

/**
 * Gives a column a role, or none. The server says if the result will not do. A new role starts in
 * the unit of the column's header, or SI, as a unit belongs to the quantity it was chosen for.
 */
export async function assignColumn(
  column: number,
  role: ColumnRole["role"] | null,
) {
  const current = store().singleFile;
  if (current === null) {
    return;
  }
  const others = requestMapping(current.mapping).filter(
    (item) => item.column !== column,
  );
  const mapping = role === null ? others : [...others, { column, role }];
  await read(current.name, current.text, mapping, current.table);
}

/** Reads a column in another unit. */
export async function chooseUnit(column: number, unit: Unit) {
  const current = store().singleFile;
  if (current === null) {
    return;
  }
  // Only units a user chose go again, so that a column read in SI by default stays marked so.
  const mapping = requestMapping(current.mapping).map((item) =>
    item.column === column ? { ...item, unit } : item,
  );
  await read(current.name, current.text, mapping, current.table);
}

export function removeSingleFile() {
  stopCurrentRequest();
  clearData();
  store().clearSingleFile();
}
