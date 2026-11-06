import { PageHeading, Panel, TwoColumns } from "@/shell/layout";
import { StatusBadge } from "@/shell/StatusBadge";
import { STRINGS } from "@/strings";

/** The frame of the fit screen. The panels fill up from FS1 onwards. */
export function FitPage() {
  const { fit } = STRINGS;
  return (
    <>
      <title>{`${fit.pageTitle} · ${STRINGS.appName}`}</title>
      <TwoColumns
        side={
          <>
            <Panel title={fit.data} />
            <Panel title={fit.model} />
          </>
        }
        main={
          <>
            <PageHeading
              title={fit.title}
              subtitle={fit.subtitle}
              status={<StatusBadge status="manual" />}
            />
            <Panel title={fit.charts} />
            <div className="flex flex-wrap items-stretch gap-4">
              <div className="min-w-0 flex-[1_1_320px]">
                <Panel title={fit.parameters} />
              </div>
              <div className="min-w-0 flex-[1_1_320px]">
                <Panel title={fit.result} />
              </div>
            </div>
          </>
        }
      />
    </>
  );
}
