import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/api/client";
import { failureMessage, issueMessage, noDataMessages } from "@/data/messages";
import { readFileText } from "@/data/readFile";
import { useSessionStore, type Quantity } from "@/session/store";

export type UploadState =
  | { status: "idle"; warnings: readonly string[] }
  | { status: "loading"; name: string }
  | { status: "failed"; name: string; errors: readonly string[] };

const IDLE: UploadState = { status: "idle", warnings: [] };

/**
 * Loads a file into one quantity of the session. A new file replaces the last one, and stops a
 * read still under way, so the last chosen is the one that counts. A file that fails clears the
 * old data, as a fit from them would look like a fit from the new file.
 */
export function useFileUpload(quantity: Quantity) {
  const setData = useSessionStore((state) => state.setData);
  const removeData = useSessionStore((state) => state.removeData);
  const [state, setState] = useState<UploadState>(IDLE);
  const current = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      current.current?.abort();
    },
    [],
  );

  const upload = useCallback(
    async (file: File) => {
      current.current?.abort();
      const controller = new AbortController();
      current.current = controller;
      const { signal } = controller;
      setState({ status: "loading", name: file.name });
      removeData(quantity);

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
        setData(quantity, {
          measurement,
          source: { kind: "file", name: file.name },
          extrapolated: false,
          text,
        });
        setState({
          status: "idle",
          warnings: parsed.warnings.map(issueMessage),
        });
      } catch (error) {
        if (!signal.aborted) {
          setState({
            status: "failed",
            name: file.name,
            errors: [failureMessage(error)],
          });
        }
      }
    },
    [quantity, removeData, setData],
  );

  const remove = useCallback(() => {
    current.current?.abort();
    removeData(quantity);
    setState(IDLE);
  }, [quantity, removeData]);

  /** For a problem found before there is a file to read, such as several dropped at once. */
  const fail = useCallback(
    (error: string) => {
      current.current?.abort();
      removeData(quantity);
      setState({ status: "failed", name: "", errors: [error] });
    },
    [quantity, removeData],
  );

  return { state, upload, remove, fail };
}
