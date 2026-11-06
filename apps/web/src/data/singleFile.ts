import { apiClient, type ParseRequest } from "@/api/client";
import { failureMessage } from "@/data/messages";
import { FileReadError, readFileText } from "@/data/readFile";
import {
  QUANTITIES,
  useSessionStore,
  type ColumnRole,
  type ParsedTable,
} from "@/session/store";

function store() {
  return useSessionStore.getState();
}

function clearData() {
  for (const quantity of QUANTITIES) {
    store().removeData(quantity);
  }
}

function applyTable(name: string, table: ParsedTable) {
  for (const quantity of QUANTITIES) {
    const measurement = table.measurements[quantity];
    if (measurement === undefined) {
      store().removeData(quantity);
    } else {
      store().setData(quantity, {
        measurement,
        source: { kind: "file", name },
        extrapolated: false,
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
  clearData();
  const body: ParseRequest = mapping === null ? { text } : { text, mapping };
  try {
    const parsed = await apiClient.postParse(body);
    if (store().singleFile?.request === request) {
      store().finishSingleFile(parsed);
      applyTable(name, parsed);
    }
  } catch (error) {
    if (store().singleFile?.request === request) {
      store().failSingleFile(failureMessage(error));
    }
  }
}

export async function loadSingleFile(file: File) {
  let text: string;
  try {
    text = await readFileText(file);
  } catch (error) {
    if (error instanceof FileReadError) {
      clearData();
      store().startSingleFile({
        name: file.name,
        text: "",
        mapping: [],
        table: null,
      });
      store().failSingleFile(failureMessage(error));
    }
    return;
  }
  await read(file.name, text, null, null);
}

export function failSingleFile(message: string) {
  clearData();
  store().startSingleFile({ name: "", text: "", mapping: [], table: null });
  store().failSingleFile(message);
}

/** Gives a column a role, or none. The server says if the result will not do. */
export async function assignColumn(
  column: number,
  role: ColumnRole["role"] | null,
) {
  const current = store().singleFile;
  if (current === null) {
    return;
  }
  const others = current.mapping.filter((item) => item.column !== column);
  const mapping = role === null ? others : [...others, { column, role }];
  await read(current.name, current.text, mapping, current.table);
}

export function removeSingleFile() {
  clearData();
  store().clearSingleFile();
}
