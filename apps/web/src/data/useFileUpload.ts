import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/api/client";
import { failureMessage, issueMessage, noDataMessages } from "@/data/messages";
import { quantityFromName } from "@/data/quantityFromName";
import { readFileText } from "@/data/readFile";
import {
  useSessionStore,
  type Quantity,
  type SessionData,
} from "@/session/store";

export type UploadState =
  | { status: "idle"; warnings: readonly string[] }
  | { status: "loading"; name: string }
  | { status: "failed"; name: string; errors: readonly string[] }
  /**
   * A file with no header, held until the user says that it holds this quantity, as values alone
   * cannot tell ρ from S. `named` is another quantity its name names, if any.
   */
  | {
      status: "confirm";
      name: string;
      entry: SessionData;
      warnings: readonly string[];
      named: Quantity | null;
    };

const IDLE: UploadState = { status: "idle", warnings: [] };

/**
 * Loads a file into one quantity of the session. A new file replaces the last one, and stops a
 * read still under way, so the last chosen is the one that counts. A file that fails clears the
 * old data, as a fit from them would look like a fit from the new file.
 */
export function useFileUpload(quantity: Quantity) {
  const setData = useSessionStore((state) => state.setData);
  const removeData = useSessionStore((state) => state.removeData);
  const readStarted = useSessionStore((state) => state.fileReadStarted);
  const readEnded = useSessionStore((state) => state.fileReadEnded);
  const [state, setState] = useState<UploadState>(IDLE);
  const current = useRef<AbortController | null>(null);
  // A file counts as on its way while it waits for an answer, so that the demo leaves it alone.
  const reading = useRef(false);
  const startRead = useCallback(() => {
    if (!reading.current) {
      reading.current = true;
      readStarted();
    }
  }, [readStarted]);
  const endRead = useCallback(() => {
    if (reading.current) {
      reading.current = false;
      readEnded();
    }
  }, [readEnded]);

  useEffect(
    () => () => {
      current.current?.abort();
      endRead();
    },
    [endRead],
  );

  const upload = useCallback(
    async (file: File) => {
      current.current?.abort();
      const controller = new AbortController();
      current.current = controller;
      const { signal } = controller;
      setState({ status: "loading", name: file.name });
      removeData(quantity);
      startRead();
      let asking = false;

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
        const measurement = parsed.measurements[quantity];
        if (parsed.errors.length > 0 || measurement === undefined) {
          setState({
            status: "failed",
            name: file.name,
            errors: noDataMessages(parsed.errors, parsed.warnings),
          });
          return;
        }
        const entry: SessionData = {
          measurement,
          source: { kind: "file", name: file.name },
          extrapolated: false,
          text,
        };
        const warnings = parsed.warnings.map(issueMessage);
        // The API leaves `headers` out where no header matches, as its contract says.
        if (parsed.headers == null) {
          const named = quantityFromName(file.name);
          asking = true;
          setState({
            status: "confirm",
            name: file.name,
            entry,
            warnings,
            named: named === quantity ? null : named,
          });
          return;
        }
        setData(quantity, entry);
        setState({ status: "idle", warnings });
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
        if (!signal.aborted && !asking) {
          endRead();
        }
      }
    },
    [endRead, quantity, removeData, setData, startRead],
  );

  /** The user says that a file with no header holds this quantity. */
  const confirm = useCallback(() => {
    if (state.status !== "confirm") {
      return;
    }
    setData(quantity, state.entry);
    setState({ status: "idle", warnings: state.warnings });
    endRead();
  }, [endRead, quantity, setData, state]);

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

  return { state, upload, confirm, remove, fail };
}
