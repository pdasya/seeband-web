import { PageHeading } from "@/shell/layout";
import { STRINGS } from "@/strings";

/** R1 fills this. */
export function ResultsPage() {
  const { results } = STRINGS;
  return (
    <>
      <title>{`${results.pageTitle} · ${STRINGS.appName}`}</title>
      <PageHeading title={results.title} subtitle={results.subtitle} />
    </>
  );
}
