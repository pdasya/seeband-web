import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { PageHeading } from "@/shell/layout";
import { STRINGS } from "@/strings";

export function NotFoundPage() {
  const { notFound } = STRINGS;
  return (
    <>
      <title>{`${notFound.pageTitle} · ${STRINGS.appName}`}</title>
      <PageHeading
        title={notFound.title}
        subtitle={notFound.text}
        actions={
          <Button asChild variant="outline">
            <Link to="/fit">{notFound.action}</Link>
          </Button>
        }
      />
    </>
  );
}

function ErrorMessage() {
  const { error } = STRINGS;
  return (
    <>
      <title>{`${error.pageTitle} · ${STRINGS.appName}`}</title>
      <PageHeading
        title={error.title}
        subtitle={error.text}
        actions={
          <Button
            variant="outline"
            onClick={() => {
              window.location.reload();
            }}
          >
            {error.action}
          </Button>
        }
      />
    </>
  );
}

/**
 * For an error in a page. It appears inside the shell, as navigation is a way out.
 *
 * Neither view shows details of the error, whose message could quote a user's data.
 */
export function PageErrorView() {
  return <ErrorMessage />;
}

/** For an error in the shell itself. So it uses nothing of the shell, or it would fail too. */
export function ShellErrorView() {
  return (
    <main className="mx-auto box-border max-w-[var(--layout-max-width)] p-6">
      <ErrorMessage />
    </main>
  );
}
