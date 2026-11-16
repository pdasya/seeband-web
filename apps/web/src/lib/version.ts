/** A version with the commit it came from, as exported files and the report name it. */
export function withCommit(
  version: string,
  commit: string | null | undefined,
): string {
  return commit === null || commit === undefined || commit === ""
    ? version
    : `${version} (commit ${commit})`;
}

/** This app's version and commit, set when it is built. */
export const APP_VERSION = withCommit(__APP_VERSION__, __APP_COMMIT__);
