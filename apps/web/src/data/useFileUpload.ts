import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/api/client";
import {
  errorsAChoiceCanMend,
  failureMessage,
  fileWarnings,
  issueMessage,
  noDataMessages,
} from "@/data/messages";
import { quantityFromName } from "@/data/quantityFromName";
import { readFileText } from "@/data/readFile";
import {
  columnOf,
  isUnitDoubt,
  unitDoubts,
  withUnit,
  type Unit,
} from "@/data/units";
import {
  chosenQuantity,
  initialRoles,
  mappingOf,
  type Role,
} from "@/data/columnChoice";
import {
  loadedAs,
  useSessionStore,
  type LoadedQuantity,
  type Quantity,
} from "@/session/store";
import { STRINGS } from "@/strings";

/** A file with no header, which waits for the user to say what its columns hold. */
export interface ColumnChoice {
  name: string;
  /** Kept to send again with the user's mapping, as the API keeps nothing. */
  text: string;
  columns: number;
  rows: number;
  firstRow: readonly number[];
  roles: readonly (Role | null)[];
  /** The unit chosen for each column, or null for SI. */
  units: readonly (Unit | null)[];
  /** Another quantity the file's name names, if any. */
  named: LoadedQuantity | null;
  /** Values below 0 for ρ, or 0 and below for σ, which the slot's quantity cannot have. */
  belowZero: "resistivity" | "conductivity" | null;
  /** A header that does not fit the columns, so the parser named none. */
  mismatch: boolean;
  /** What stays true of the file whatever its columns hold. */
  fileWarnings: readonly string[];
  problems: readonly string[];
  applying: boolean;
}

export type UploadState =
  | {
      status: "idle";
      warnings: readonly string[];
      /** The loaded file is read again in another unit. */
      rereading?: boolean;
      /** Why it could not be, while its data stay as they were. */
      failures?: readonly string[];
    }
  | { status: "loading"; name: string }
  | { status: "failed"; name: string; errors: readonly string[] }
  | ({ status: "choose" } & ColumnChoice);

const IDLE: UploadState = { status: "idle", warnings: [] };

type ChoiceState = Extract<UploadState, { status: "choose" }>;

type Issue = Parameters<typeof issueMessage>[0];

/** Warnings shown under a file. A doubt about its unit shows on its own, as an alert. */
function listedWarnings(warnings: readonly Issue[]): string[] {
  return warnings.filter(({ code }) => !isUnitDoubt(code)).map(issueMessage);
}

/**
 * Loads a file into one quantity of the session. A new file replaces the last one, and stops a
 * read still under way, so the last chosen is the one that counts. A file that fails clears the
 * old data, as a fit from them would look like a fit from the new file.
 *
 * A file with no header waits for the user to choose what its columns hold, as values alone cannot
 * tell ρ from S. A choice of another quantity puts the file in that quantity's slot. `expected` is
 * what the slot reads a file with no header as: σ in place of ρ, which the server turns into 1/σ.
 */
export function useFileUpload(
  quantity: Quantity,
  expected: LoadedQuantity = quantity,
) {
  const setData = useSessionStore((state) => state.setData);
  const removeData = useSessionStore((state) => state.removeData);
  const readStarted = useSessionStore((state) => state.fileReadStarted);
  const readEnded = useSessionStore((state) => state.fileReadEnded);
  const [state, setState] = useState<UploadState>(IDLE);
  const current = useRef<AbortController | null>(null);
  // A file counts as on its way while it waits for a choice, so that the demo leaves it alone.
  const reading = useRef(false);
  const startRead = useCallback(() => {
    if (!reading.current) {
      reading.current = true;
      readStarted(quantity);
    }
  }, [quantity, readStarted]);
  const endRead = useCallback(() => {
    if (reading.current) {
      reading.current = false;
      readEnded(quantity);
    }
  }, [quantity, readEnded]);

  useEffect(
    () => () => {
      current.current?.abort();
      endRead();
    },
    [endRead],
  );

  const newRequest = () => {
    current.current?.abort();
    const controller = new AbortController();
    current.current = controller;
    return controller.signal;
  };

  const upload = useCallback(
    async (file: File) => {
      const signal = newRequest();
      setState({ status: "loading", name: file.name });
      removeData(quantity);
      startRead();
      let choosing = false;

      try {
        const text = await readFileText(file);
        if (signal.aborted) {
          return;
        }
        const parsed = await apiClient.postParse({ text, expected }, signal);
        if (signal.aborted) {
          return;
        }
        // The API leaves `headers` out where no header matches, as its contract says.
        if (parsed.headers == null && errorsAChoiceCanMend(parsed.errors)) {
          const named = quantityFromName(file.name);
          const other = named === expected ? null : named;
          const codes = new Set(parsed.errors.map(({ code }) => code));
          const belowZero = codes.has("negative_resistivity")
            ? "resistivity"
            : codes.has("non_positive_conductivity")
              ? "conductivity"
              : null;
          choosing = true;
          setState({
            status: "choose",
            name: file.name,
            text,
            columns: parsed.column_count,
            rows: parsed.row_count,
            firstRow: parsed.preview[0] ?? [],
            roles: initialRoles(parsed.column_count),
            units: Array.from({ length: parsed.column_count }, () => null),
            named: other,
            belowZero,
            mismatch: parsed.warnings.some(
              ({ code }) => code === "header_mismatch",
            ),
            fileWarnings: fileWarnings(parsed.warnings).map(issueMessage),
            problems: [],
            applying: false,
          });
          return;
        }
        const measurement = parsed.measurements[quantity];
        if (parsed.errors.length > 0 || measurement === undefined) {
          setState({
            status: "failed",
            name: file.name,
            errors: noDataMessages(parsed.errors, parsed.warnings),
          });
          return;
        }
        setData(quantity, {
          measurement,
          source: { kind: "file", name: file.name },
          extrapolated: false,
          text,
          readAs: parsed.mapping,
          unitDoubts: unitDoubts(
            parsed.warnings,
            columnOf(parsed.mapping, loadedAs(quantity, { measurement })),
          ),
        });
        setState({
          status: "idle",
          warnings: listedWarnings(parsed.warnings),
        });
      } catch (error) {
        if (!signal.aborted) {
          setState({
            status: "failed",
            name: file.name,
            errors: [failureMessage(error)],
          });
        }
      } finally {
        // A newer file or a removal has taken over the count of an aborted one.
        if (!signal.aborted && !choosing) {
          endRead();
        }
      }
    },
    [endRead, expected, quantity, removeData, setData, startRead],
  );

  /** Reads the file again with the user's choice, into the slot of the quantity chosen. */
  const applyChoice = useCallback(
    async (choice: ChoiceState) => {
      const target = chosenQuantity(choice.roles);
      if (target === null) {
        return;
      }
      const { data: text } = STRINGS;
      // The slot's name, which a σ file takes as ρ = 1/σ.
      const title = text.quantities[target].title;
      const session = useSessionStore.getState();
      // Another slot with a file of its own on the way would write over this one later.
      const problem =
        target === quantity
          ? null
          : session.slotsReading.includes(target)
            ? text.slotBusy(title)
            : session.data[target] !== undefined
              ? text.slotTaken(title)
              : null;
      if (problem !== null) {
        setState({ ...choice, problems: [problem] });
        return;
      }
      const signal = newRequest();
      setState({ ...choice, applying: true, problems: [] });
      const mapping = mappingOf(choice.roles, choice.units);
      try {
        const parsed = await apiClient.postParse(
          { text: choice.text, mapping },
          signal,
        );
        if (signal.aborted) {
          return;
        }
        const measurement = parsed.measurements[target];
        if (parsed.errors.length > 0 || measurement === undefined) {
          setState({
            ...choice,
            applying: false,
            problems: noDataMessages(parsed.errors, parsed.warnings),
          });
          return;
        }
        setData(target, {
          measurement,
          source: { kind: "file", name: choice.name },
          extrapolated: false,
          text: choice.text,
          mapping,
          readAs: parsed.mapping,
          unitDoubts: unitDoubts(
            parsed.warnings,
            columnOf(parsed.mapping, loadedAs(target, { measurement })),
          ),
        });
        setState(
          target === quantity
            ? {
                status: "idle",
                warnings: [
                  ...new Set([
                    ...choice.fileWarnings,
                    ...listedWarnings(parsed.warnings),
                  ]),
                ],
              }
            : IDLE,
        );
        endRead();
      } catch (error) {
        if (!signal.aborted) {
          setState({
            ...choice,
            applying: false,
            problems: [failureMessage(error)],
          });
        }
      }
    },
    [endRead, quantity, setData],
  );

  /** Sets a new choice, and reads the file at once if it has T and one quantity. */
  const choose = useCallback(
    (change: (choice: ChoiceState) => ChoiceState): boolean => {
      if (state.status !== "choose" || state.applying) {
        return false;
      }
      const next = { ...change(state), problems: [] };
      setState(next);
      if (chosenQuantity(next.roles) === null) {
        return false;
      }
      void applyChoice(next);
      return true;
    },
    [applyChoice, state],
  );

  /**
   * What one column holds, or nothing. A choice of T and one quantity reads the file at once, as
   * for a single table: choosing is the user's confirmation, so nothing is chosen for them.
   * Returns whether the file is read.
   */
  const chooseRole = useCallback(
    (column: number, role: Role | null) =>
      choose((choice) => ({
        ...choice,
        roles: choice.roles.map((old, index) =>
          index === column ? role : old,
        ),
        // A unit belongs to the role it was chosen for.
        units: choice.units.map((old, index) =>
          index === column ? null : old,
        ),
      })),
    [choose],
  );

  /**
   * The unit one column of a file with no header is written in. With T and one quantity chosen, it
   * reads the file again, as after a problem the unit may be what mends it.
   */
  const chooseColumnUnit = useCallback(
    (column: number, unit: Unit) =>
      choose((choice) => ({
        ...choice,
        units: choice.units.map((old, index) =>
          index === column ? unit : old,
        ),
      })),
    [choose],
  );

  /** Reads the same choice again, once what was wrong with it, such as a full slot, is mended. */
  const retryChoice = useCallback(() => choose((choice) => choice), [choose]);

  /**
   * Reads the loaded file again with its values in another unit. A failure keeps the data as they
   * were, in the unit the card still shows.
   */
  const changeUnit = useCallback(
    async (role: Role, unit: Unit) => {
      const entry = useSessionStore.getState().data[quantity];
      if (entry?.readAs === undefined || reading.current) {
        return;
      }
      const mapping = withUnit(entry.mapping ?? entry.readAs, role, unit);
      const signal = newRequest();
      // Counted as on its way, and the selects wait, so that a second change cannot start from
      // the old units, and the demo leaves the slot alone.
      startRead();
      setState((previous) =>
        previous.status === "idle"
          ? { ...previous, rereading: true, failures: [] }
          : previous,
      );
      const failed = (failures: string[]) => {
        setState((previous) =>
          previous.status === "idle"
            ? { ...previous, rereading: false, failures }
            : previous,
        );
      };
      try {
        const parsed = await apiClient.postParse(
          { text: entry.text, mapping },
          signal,
        );
        if (signal.aborted) {
          return;
        }
        const measurement = parsed.measurements[quantity];
        if (parsed.errors.length > 0 || measurement === undefined) {
          failed(noDataMessages(parsed.errors, parsed.warnings));
          return;
        }
        setData(quantity, {
          ...entry,
          measurement,
          mapping,
          readAs: parsed.mapping,
          unitDoubts: unitDoubts(
            parsed.warnings,
            columnOf(parsed.mapping, loadedAs(quantity, { measurement })),
          ),
        });
        setState({ status: "idle", warnings: listedWarnings(parsed.warnings) });
      } catch (error) {
        if (!signal.aborted) {
          failed([failureMessage(error)]);
        }
      } finally {
        // A newer file or a removal has taken over the count of an aborted read.
        if (!signal.aborted) {
          endRead();
        }
      }
    },
    [endRead, quantity, setData, startRead],
  );

  const remove = useCallback(() => {
    current.current?.abort();
    removeData(quantity);
    setState(IDLE);
    endRead();
  }, [endRead, quantity, removeData]);

  /** For a problem found before there is a file to read, such as several dropped at once. */
  const fail = useCallback(
    (error: string) => {
      current.current?.abort();
      removeData(quantity);
      setState({ status: "failed", name: "", errors: [error] });
      endRead();
    },
    [endRead, quantity, removeData],
  );

  return {
    state,
    upload,
    chooseRole,
    chooseColumnUnit,
    retryChoice,
    changeUnit,
    remove,
    fail,
  };
}
