import { offersExplicitDpb } from "@/model/selection";
import {
  convertedSession,
  historicalSource,
  type HallMassConvention,
  legacyVector,
  withoutLegacyDpb,
} from "@/session/legacyDpb";
import { FolderOpenIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { apiClient, type FitRequest } from "@/api/client";
import { useModels } from "@/api/queries";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatNumber, parseNumber } from "@/lib/numbers";
import type { SessionFile } from "@/session/sessionFile";
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

type Problem = SessionFileProblem | "read_failed" | "migration_failed";

/**
 * Opens a session file in place of this session, after `readSessionFile` has checked it. The
 * server's core is asked for once, so that the fit screen can say when it differs from the core
 * the file's fit ran on.
 */
function useSessionOpen() {
  const restore = useSessionStore((state) => state.restoreSession);
  const { data: catalog } = useModels();
  const [pending, setPending] = useState<SessionFile | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [archivedDpb, setArchivedDpb] = useState(false);

  const open = async (file: File) => {
    setBusy(true);
    setProblem(null);
    setArchivedDpb(false);
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
      if (
        session.content.selection.model === "dpb" &&
        session.content.selection.parameterization === undefined
      ) {
        const models =
          catalog ??
          (await apiClient.getModels(undefined, "explicit_fermi_v1"));
        if (models.models.some(offersExplicitDpb)) {
          setPending(session);
          return;
        }
      }
      const dormantDpb =
        session.content.selection.parameterization === undefined &&
        session.content.selection.model !== "dpb" &&
        ([
          session.content.parameters,
          session.content.customBounds,
          session.content.held,
          session.content.guessedParameters ?? {},
        ].some((modes) =>
          Object.keys(modes).some((mode) => mode.startsWith("dpb_")),
        ) ||
          session.content.savedModelSettings?.dpb !== undefined) &&
        (
          catalog ?? (await apiClient.getModels(undefined, "explicit_fermi_v1"))
        ).models.some(offersExplicitDpb);
      const content = dormantDpb
        ? {
            ...session.content,
            selection: {
              ...session.content.selection,
              legacySource:
                session.content.selection.legacySource ??
                historicalSource(session),
            },
            parameters: withoutLegacyDpb(session.content.parameters),
            guessedParameters: withoutLegacyDpb(
              session.content.guessedParameters ?? {},
            ),
            customBounds: withoutLegacyDpb(session.content.customBounds),
            held: withoutLegacyDpb(session.content.held),
            savedModelSettings: Object.fromEntries(
              Object.entries(session.content.savedModelSettings ?? {}).filter(
                ([id]) => id !== "dpb",
              ),
            ),
          }
        : session.content;
      setArchivedDpb(dormantDpb);
      const server = await apiClient.getHealth().catch(() => null);
      restore(restoredSession(content), {
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

  const convert = async (
    m1: number,
    band1: number,
    band2: number,
    convention?: HallMassConvention,
  ) => {
    if (pending === null) return;
    setBusy(true);
    try {
      const content = pending.content;
      const legacyModels = await apiClient.getModels();
      const description = legacyModels.models
        .find((model) => model.id === "dpb")
        ?.fit_modes.find((mode) => mode.id === content.selection.fitMode);
      if (!description) throw new Error("Legacy mode unavailable");
      const vector = legacyVector(content, description);
      const fermiEnergyK = vector.fermi_energy;
      if (fermiEnergyK === undefined) throw new Error("Legacy EF unavailable");
      const converted = await apiClient.migrateDpb({
        parameters: vector,
        m1,
        band_1_degeneracy: band1,
        band_2_degeneracy: band2,
      });
      const server = await apiClient.getHealth().catch(() => null);
      const restored = restoredSession(
        convertedSession(
          pending,
          converted,
          band1,
          band2,
          fermiEnergyK,
          convention,
        ),
      );
      restore(restored, {
        saved: pending.saved,
        appVersion: pending.appVersion,
        fitCoreVersion: null,
        serverCoreVersion: server?.core_version ?? null,
      });
      setPending(null);
    } catch {
      setProblem("migration_failed");
    } finally {
      setBusy(false);
    }
  };
  return {
    open,
    busy,
    problem,
    pending,
    archivedDpb,
    cancel: () => {
      setPending(null);
      setProblem(null);
    },
    convert,
  };
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
  const { data: models } = useModels();
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
  const { open, busy, problem, pending, cancel, convert, archivedDpb } =
    useSessionOpen();
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
      {pending && (
        <LegacyMigration
          key={pending.checksum}
          session={pending}
          busy={busy}
          failed={problem === "migration_failed"}
          onCancel={cancel}
          onConvert={convert}
        />
      )}
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
        {problem === null
          ? ""
          : problem === "migration_failed"
            ? STRINGS.explicitDpb.migrationFailed
            : text.problems[problem]}
      </p>
      {archivedDpb && (
        <p role="status" className="m-0 text-xs text-muted-foreground">
          {text.archivedDpb}
        </p>
      )}
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

function LegacyMigration({
  session,
  busy,
  failed,
  onCancel,
  onConvert,
}: {
  session: SessionFile;
  busy: boolean;
  failed: boolean;
  onCancel: () => void;
  onConvert: (
    mass: number,
    band1: number,
    band2: number,
    hallMassConvention?: HallMassConvention,
  ) => Promise<void>;
}) {
  const text = STRINGS.explicitDpb;
  const mode = session.content.selection.fitMode ?? "dpb_s_rho";
  const vector = legacyVector(session.content);
  const hallMass = mode === "dpb_s_rho_rh" ? vector?.m1 : undefined;
  const hasHallMass = hallMass !== undefined && hallMass > 0;
  const savedN1 =
    session.content.fit?.request?.band_1_degeneracy ??
    session.content.selection.band1Degeneracy;
  const [convention, setConvention] = useState<HallMassConvention | "">(
    savedN1 === 1 ? "single_valley" : "",
  );
  const [mass, setMass] = useState("");
  const [n1, setN1] = useState(
    String(
      session.content.fit?.request?.band_1_degeneracy ??
        session.content.selection.band1Degeneracy,
    ),
  );
  const [n2, setN2] = useState(
    String(
      session.content.fit?.request?.band_2_degeneracy ??
        session.content.selection.band2Degeneracy,
    ),
  );
  // An older all-valley DOS mass includes the multiplicity at the time it
  // was saved, independently of the multiplicities confirmed for the new fit.
  const massValue = hasHallMass
    ? convention === ""
      ? null
      : convention === "all_valley"
        ? hallMass / Math.cbrt(savedN1) ** 2
        : hallMass
    : parseNumber(mass);
  const band1Value = parseNumber(n1);
  const band2Value = parseNumber(n2);
  const valid =
    massValue !== null &&
    Number.isFinite(massValue) &&
    massValue > 0 &&
    band1Value !== null &&
    band1Value > 0 &&
    Number.isInteger(band1Value) &&
    band2Value !== null &&
    band2Value > 0 &&
    Number.isInteger(band2Value);
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) onCancel();
      }}
    >
      <DialogContent closeLabel={text.cancel}>
        <DialogHeader>
          <DialogTitle>{text.migrationTitle}</DialogTitle>
          <DialogDescription>{text.migrationHint}</DialogDescription>
        </DialogHeader>
        {hasHallMass && (
          <>
            <p className="text-sm">
              {text.savedHallMass(
                formatNumber(hallMass),
                formatNumber(savedN1),
              )}
            </p>
            {savedN1 !== 1 && (
              <label>
                {text.hallMassConvention}
                <select
                  className="rounded-md border bg-background px-2 py-1"
                  value={convention}
                  disabled={busy}
                  onChange={(event) =>
                    setConvention(event.target.value as HallMassConvention | "")
                  }
                >
                  <option value="">{text.chooseHallMassConvention}</option>
                  <option value="single_valley">{text.singleValleyMass}</option>
                  <option value="all_valley">{text.allValleyMass}</option>
                </select>
              </label>
            )}
            <p className="text-sm text-muted-foreground">{text.hallMassHint}</p>
          </>
        )}
        <label>
          {text.mass}
          <Input
            value={
              hasHallMass
                ? massValue === null
                  ? ""
                  : formatNumber(massValue)
                : mass
            }
            disabled={busy || hasHallMass}
            onChange={(event) => setMass(event.target.value)}
          />
        </label>
        <label>
          {STRINGS.fit.degeneracyOf(1)}
          <Input
            value={n1}
            disabled={busy}
            onChange={(event) => setN1(event.target.value)}
          />
        </label>
        <label>
          {STRINGS.fit.degeneracyOf(2)}
          <Input
            value={n2}
            disabled={busy}
            onChange={(event) => setN2(event.target.value)}
          />
        </label>
        {failed && (
          <p role="alert" className="text-sm text-destructive">
            {text.migrationFailed}
          </p>
        )}
        <Button
          disabled={busy || !valid}
          onClick={() => {
            if (valid)
              void onConvert(
                massValue,
                band1Value,
                band2Value,
                hasHallMass ? convention || undefined : undefined,
              );
          }}
        >
          {text.confirm}
        </Button>
        <Button variant="outline" disabled={busy} onClick={onCancel}>
          {text.cancel}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
