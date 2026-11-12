import { flushSync } from "react-dom";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { useDemoData } from "@/data/useDemoData";
import {
  QUANTITIES,
  holdsFiles,
  readsFiles,
  useSessionStore,
} from "@/session/store";
import { STRINGS } from "@/strings";

const { data: text } = STRINGS;

/** What a demo says about itself, by the key the API gives. */
export function noticeText(messageKey: string): string {
  const known: Record<string, string> = text.demoNotices;
  return known[messageKey] ?? text.demoNoticeOther;
}

function Line({ children }: { children: string }) {
  return <p className="m-0 text-xs text-muted-foreground">{children}</p>;
}

/** Says that demo data are not a measurement, for as long as any are in use. */
export function DemoNotice() {
  const { wanted, loading, failed } = useDemoData();
  const data = useSessionStore((state) => state.data);
  const hasFiles = useSessionStore(holdsFiles);
  const reading = useSessionStore(readsFiles);
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
      {!wanted && !hasFiles && !reading && (
        <Button variant="link" size="sm" className="self-start px-0" asChild>
          <Link to="/fit?demo=1">{text.demoTry}</Link>
        </Button>
      )}
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
              // The slots must show their empty state before focus moves, or it lands on a demo
              // card that is about to go, and falls to the page.
              flushSync(() => {
                for (const quantity of demo) {
                  removeData(quantity);
                }
              });
              // The button goes away with the demo, so focus moves on to the first slot's control.
              document
                .querySelector<HTMLElement>(
                  "[data-file-slot] input, [data-file-slot] button",
                )
                ?.focus();
            }}
          >
            {text.demoClear}
          </Button>
        </div>
      )}
    </div>
  );
}
