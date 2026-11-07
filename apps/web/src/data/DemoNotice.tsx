import { Button } from "@/components/ui/button";
import { useDemoData } from "@/data/useDemoData";
import { QUANTITIES, holdsFiles, useSessionStore } from "@/session/store";
import { STRINGS } from "@/strings";

const { data: text } = STRINGS;

function noticeText(messageKey: string): string {
  const known: Record<string, string> = text.demoNotices;
  return known[messageKey] ?? text.demoNoticeOther;
}

function Line({ children }: { children: string }) {
  return <p className="m-0 text-xs text-muted-foreground">{children}</p>;
}

/** Says that demo data are not a measurement, for as long as any are in use. */
export function DemoNotice() {
  const { loading, failed } = useDemoData();
  const data = useSessionStore((state) => state.data);
  const hasFiles = useSessionStore(holdsFiles);
  const removeData = useSessionStore((state) => state.removeData);

  const demo = QUANTITIES.filter(
    (quantity) => data[quantity]?.source.kind === "demo",
  );
  const source = demo[0] === undefined ? undefined : data[demo[0]]?.source;

  return (
    <div className="mt-2.5 flex flex-col gap-2 empty:hidden">
      {loading && (
        <p role="status" className="m-0 text-xs text-muted-foreground">
          {text.demoLoading}
        </p>
      )}
      {failed && !hasFiles && <Line>{text.demoFailed}</Line>}
      {source?.kind === "demo" && (
        <div
          role="status"
          className="flex flex-col items-start gap-2 rounded-lg border px-3 py-2.5"
        >
          <Line>{noticeText(source.messageKey)}</Line>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              for (const quantity of demo) {
                removeData(quantity);
              }
            }}
          >
            {text.demoClear}
          </Button>
        </div>
      )}
    </div>
  );
}
