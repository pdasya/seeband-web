import { FolderOpenIcon } from "lucide-react";
import { useRef, useState } from "react";

import { apiClient } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  readSessionFile,
  type SessionFileProblem,
} from "@/session/sessionFile";
import { useSessionStore } from "@/session/store";
import { STRINGS } from "@/strings";

const text = STRINGS.session;

/** The largest session file opened, as its text: data of three files and their tables. */
const MAX_FILE_BYTES = 60_000_000;

/**
 * Opens a session file in place of this session, after `readSessionFile` has checked it. The
 * server's core is asked for once, so that the fit screen can say when it differs from the core
 * the file's fit ran on.
 */
export function useSessionOpen() {
  const restore = useSessionStore((state) => state.restoreSession);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<
    SessionFileProblem | "read_failed" | null
  >(null);

  const open = async (file: File) => {
    setBusy(true);
    setProblem(null);
    try {
      if (file.size > MAX_FILE_BYTES) {
        setProblem("too_large");
        return;
      }
      let contents: string;
      try {
        contents = await file.text();
      } catch {
        setProblem("read_failed");
        return;
      }
      const read = await readSessionFile(contents);
      if ("problem" in read) {
        setProblem(read.problem);
        return;
      }
      const { session } = read;
      const server = await apiClient.getHealth().catch(() => null);
      restore(
        {
          dataMode: session.dataMode,
          data: session.data,
          singleFile: session.singleFile,
          selection: session.selection,
          parameters: session.parameters,
          customBounds: session.customBounds,
          held: session.held,
          interpolationEnabled: session.interpolation.enabled,
          fitStart: session.fitStart,
          result: session.fit?.result ?? null,
        },
        {
          saved: session.saved,
          appVersion: session.appVersion,
          fitCoreVersion: session.fit?.result.core_version ?? null,
          serverCoreVersion: server?.core_version ?? null,
        },
      );
    } finally {
      setBusy(false);
    }
  };

  return { open, busy, problem };
}

/** The Open session button, what went wrong with a file, and what a restored session came from. */
export function SessionOpen() {
  const input = useRef<HTMLInputElement>(null);
  const { open, busy, problem } = useSessionOpen();
  const restored = useSessionStore((state) => state.restored);
  const fit = useSessionStore((state) => state.fit);
  return (
    <div className="mt-3 flex flex-col gap-1.5">
      <div>
        <input
          ref={input}
          type="file"
          accept=".json,application/json"
          hidden
          aria-hidden="true"
          tabIndex={-1}
          onChange={(event) => {
            const file = event.target.files?.[0];
            // The same file can be chosen again, after a fix.
            event.target.value = "";
            if (file !== undefined) {
              void open(file);
            }
          }}
        />
        <Button
          variant="outline"
          size="sm"
          disabled={busy}
          title={text.openHint}
          onClick={() => input.current?.click()}
        >
          <FolderOpenIcon aria-hidden="true" />
          {busy ? text.opening : text.open}
        </Button>
      </div>
      <p role="status" className="m-0 text-xs text-destructive empty:hidden">
        {problem === null ? "" : text.problems[problem]}
      </p>
      {restored !== null && (
        <p className="m-0 text-xs text-muted-foreground">
          {text.restored(
            new Date(restored.saved).toLocaleString("en-GB"),
            restored.appVersion,
          )}
          {fit.status === "done" && restored.fitCoreVersion !== null && (
            <>
              {" "}
              {text.restoredFit(restored.fitCoreVersion)}
              {restored.serverCoreVersion !== null &&
                restored.serverCoreVersion !== restored.fitCoreVersion && (
                  <> {text.otherCore(restored.serverCoreVersion)}</>
                )}
            </>
          )}
        </p>
      )}
    </div>
  );
}
