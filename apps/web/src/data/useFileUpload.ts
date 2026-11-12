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
import { looksLikeAnotherUnit, withUnit, type Unit } from "@/data/units";
import {
  chosenQuantity,
  initialRoles,
  mappingOf,
  type Role,
} from "@/data/columnChoice";
import { useSessionStore, type Quantity } from "@/session/store";
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
  named: Quantity | null;
  /** Values below 0 in a ρ slot, which a resistivity cannot have. */
  negative: boolean;
  /** A header that does not fit the columns, so the parser named none. */
  mismatch: boolean;
  /** What stays true of the file whatever its columns hold. */
  fileWarnings: readonly string[];
  problems: readonly string[];
  applying: boolean;
}

export type UploadState =
  | { status: "idle"; warnings: readonly string[] }
  | { status: "loading"; name: string }
  | { status: "failed"; name: string; errors: readonly string[] }
  | ({ status: "choose" } & ColumnChoice);

const IDLE: UploadState = { status: "idle", warnings: [] };

type ChoiceState = Extract<UploadState, { status: "choose" }>;

type Issue = Parameters<typeof issueMessage>[0];

/** Warnings shown under a file. One about its unit shows on its own, as an alert. */
function listedWarnings(warnings: readonly Issue[]): string[] {
  return warnings
    .filter(({ code }) => code !== "implausible_magnitude")
    .map(issueMessage);
}

/**
 * Loads a file into one quantity of the session. A new file replaces the last one, and stops a
 * read still under way, so the last chosen is the one that counts. A file that fails clears the
 * old data, as a fit from them would look like a fit from the new file.
 *
 * A file with no header waits for the user to choose what its columns hold, as values alone cannot
 * tell ρ from S. A choice of another quantity puts the file in that quantity's slot.
 */
export function useFileUpload(quantity: Quantity) {
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
        const parsed = await apiClient.postParse(
          { text, expected: quantity },
          signal,
        );
        if (signal.aborted) {
          return;
        }
        // The API leaves `headers` out where no header matches, as its contract says.
        if (parsed.headers == null && errorsAChoiceCanMend(parsed.errors)) {
          const named = quantityFromName(file.name);
          const other = named === quantity ? null : named;
          const negative = parsed.errors.some(
            ({ code }) => code === "negative_resistivity",
          );
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
            negative,
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
          implausible: looksLikeAnotherUnit(parsed.warnings, undefined),
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
    [endRead, quantity, removeData, setData, startRead],
  );

  /** The unit one column of a file with no header is written in. */
  const chooseColumnUnit = useCallback((column: number, unit: Unit) => {
    setState((previous) =>
      previous.status === "choose"
        ? {
            ...previous,
            units: previous.units.map((old, index) =>
              index === column ? unit : old,
            ),
            problems: [],
          }
        : previous,
    );
  }, []);

  /** Reads the file again with the user's choice, into the slot of the quantity chosen. */
  const applyChoice = useCallback(
    async (choice: ChoiceState) => {
      const target = chosenQuantity(choice.roles);
      if (target === null) {
        return;
      }
      const { data: text } = STRINGS;
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
          implausible: looksLikeAnotherUnit(parsed.warnings, undefined),
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

  /**
   * What one column holds, or nothing. A choice of T and one quantity reads the file at once, as
   * for a single table: choosing is the user's confirmation, so nothing is chosen for them.
   */
  const chooseRole = useCallback(
    (column: number, role: Role | null) => {
      if (state.status !== "choose" || state.applying) {
        return;
      }
      const next: ChoiceState = {
        ...state,
        roles: state.roles.map((old, index) => (index === column ? role : old)),
        // A unit belongs to the role it was chosen for.
        units: state.units.map((old, index) => (index === column ? null : old)),
        problems: [],
      };
      setState(next);
      if (chosenQuantity(next.roles) !== null) {
        void applyChoice(next);
      }
    },
    [applyChoice, state],
  );

  /**
   * Reads the loaded file again with its values in another unit. A failure keeps the data as they
   * were, in the unit the card still shows.
   */
  const changeUnit = useCallback(
    async (role: Role, unit: Unit) => {
      const entry = useSessionStore.getState().data[quantity];
      if (entry?.readAs === undefined) {
        return;
      }
      const mapping = withUnit(entry.mapping ?? entry.readAs, role, unit);
      const signal = newRequest();
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
          setState({
            status: "idle",
            warnings: noDataMessages(parsed.errors, parsed.warnings),
          });
          return;
        }
        setData(quantity, {
          ...entry,
          measurement,
          mapping,
          readAs: parsed.mapping,
          implausible: looksLikeAnotherUnit(parsed.warnings, undefined),
        });
        setState({ status: "idle", warnings: listedWarnings(parsed.warnings) });
      } catch (error) {
        if (!signal.aborted) {
          setState({ status: "idle", warnings: [failureMessage(error)] });
        }
      }
    },
    [quantity, setData],
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
    changeUnit,
    remove,
    fail,
  };
}
