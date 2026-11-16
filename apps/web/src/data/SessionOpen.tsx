import { useQuery } from "@tanstack/react-query";
import { FolderOpenIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { apiClient, type FitRequest } from "@/api/client";
import { modelsQuery } from "@/api/queries";
import { Button } from "@/components/ui/button";
import { fitRequest } from "@/model/fitRequest";
import {
  canonical,
  MAX_SESSION_BYTES,
  readSessionFile,
  restoredSession,
  type SessionFileProblem,
} from "@/session/sessionFile";
import { isFitActive, readsFiles, useSessionStore } from "@/session/store";
import { STRINGS } from "@/strings";

const text = STRINGS.session;

type Problem = SessionFileProblem | "read_failed";

/**
 * Opens a session file in place of this session, after `readSessionFile` has checked it. The
 * server's core is asked for once, so that the fit screen can say when it differs from the core
 * the file's fit ran on.
 */
function useSessionOpen() {
  const restore = useSessionStore((state) => state.restoreSession);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  const open = async (file: File) => {
    setBusy(true);
    setProblem(null);
    try {
      if (file.size > MAX_SESSION_BYTES) {
        setProblem("too_large");
        return;
      }
      const read = await readSessionFile(await file.text());
      if ("problem" in read) {
        setProblem(read.problem);
        return;
      }
      const { session } = read;
      const server = await apiClient.getHealth().catch(() => null);
      restore(restoredSession(session.content), {
        saved: session.saved,
        appVersion: session.appVersion,
        fitCoreVersion: session.content.fit?.result.core_version ?? null,
        serverCoreVersion: server?.core_version ?? null,
      });
    } catch {
      // A file that cannot be read, or a digest that fails, opens nothing.
      setProblem("read_failed");
    } finally {
      setBusy(false);
    }
  };

  return { open, busy, problem };
}

/** A request's inputs, all but where it starts, which a fit run again from it would change. */
function inputsOf(request: FitRequest): string {
  const inputs: Partial<FitRequest> = { ...request };
  delete inputs.start;
  // With sorted keys, as a file read back need not keep the order its keys were written in.
  return canonical(inputs);
}

/**
 * Takes the restored fit off the screen once the inputs this server gives differ from those it
 * used, as a newer server can interpolate otherwise, or offer the mode no longer. It waits while
 * interpolation is on its way, and checks each time the inputs change.
 */
function useStaleRestoredFit() {
  const { data: models } = useQuery(modelsQuery);
  const restored = useSessionStore((state) => state.restored);
  const fit = useSessionStore((state) => state.fit);
  const selection = useSessionStore((state) => state.selection);
  const data = useSessionStore((state) => state.data);
  const interpolation = useSessionStore((state) => state.interpolation);
  const customBounds = useSessionStore((state) => state.customBounds);
  const held = useSessionStore((state) => state.held);
  const fitStartValues = useSessionStore((state) => state.fitStartValues);
  const stale = useSessionStore((state) => state.restoredFitStale);

  useEffect(() => {
    const kept = restored?.request ?? null;
    if (
      models === undefined ||
      restored === null ||
      kept === null ||
      fit.status !== "done" ||
      fit.result !== restored.result ||
      selection.fitMode === null ||
      fitStartValues === null
    ) {
      return;
    }
    const built = fitRequest(
      {
        selection,
        data,
        interpolation,
        customBounds,
        held,
        parameters: { [selection.fitMode]: fitStartValues },
      },
      models.models,
    );
    if ("blocked" in built) {
      // Values on their way say nothing yet; a mode or data the fit had and this server lacks do.
      if (built.blocked.reason !== "interpolating") {
        stale();
      }
      return;
    }
    if (inputsOf(built.request) !== inputsOf(kept)) {
      stale();
    }
  }, [
    models,
    restored,
    fit,
    selection,
    data,
    interpolation,
    customBounds,
    held,
    fitStartValues,
    stale,
  ]);
}

/** Opens a file chooser, with no input left in the page, as a file slot's input is the page's own. */
function chooseFile(onChosen: (file: File) => void) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json,application/json";
  input.addEventListener("change", () => {
    const file = input.files?.[0];
    if (file !== undefined) {
      onChosen(file);
    }
  });
  input.click();
}

/** The Open session button, what went wrong with a file, and what a restored session came from. */
export function SessionOpen() {
  const { open, busy, problem } = useSessionOpen();
  useStaleRestoredFit();
  const restored = useSessionStore((state) => state.restored);
  const fit = useSessionStore((state) => state.fit);
  // A fit or a file on its way would end in the restored session, so they finish first.
  const working = useSessionStore(
    (state) =>
      isFitActive(state.fit) ||
      readsFiles(state) ||
      state.singleFile?.loading === true,
  );
  const shown =
    restored !== null &&
    fit.status === "done" &&
    fit.result === restored.result &&
    restored.fitCoreVersion !== null;
  return (
    <div className="mt-3 flex flex-col gap-1.5">
      <div>
        <Button
          variant="outline"
          size="sm"
          disabled={busy || working}
          title={working ? text.waitFirst : text.openHint}
          onClick={() => {
            chooseFile((file) => void open(file));
          }}
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
          {shown && (
            <>
              {" "}
              {text.restoredFit(restored.fitCoreVersion ?? "")}{" "}
              {restored.serverCoreVersion === null
                ? text.coreUnknown
                : restored.serverCoreVersion !== restored.fitCoreVersion
                  ? text.otherCore(restored.serverCoreVersion)
                  : ""}
            </>
          )}
          {restored.stale && <> {text.stale}</>}
        </p>
      )}
    </div>
  );
}
