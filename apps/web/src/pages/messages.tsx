import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { AppShell } from "@/shell/AppShell";
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

/**
 * Shows no details of the error, whose message could quote a user's data. The shell stays, as the
 * error may lie in a page, and navigation is the way out of it.
 */
export function ErrorPage() {
  const { error } = STRINGS;
  return (
    <AppShell>
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
    </AppShell>
  );
}
