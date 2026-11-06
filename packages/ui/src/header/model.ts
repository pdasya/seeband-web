/** What the header shows. Both wrappers take this, so that they cannot offer different things. */
export interface HeaderLink {
  id: string;
  label: string;
  href: string;
  current?: boolean;
}

export interface HeaderLanguage {
  code: string;
  /** Short, as on the button, such as `EN`. */
  label: string;
  /** Full, for a screen reader, such as `English`. */
  name: string;
}

export interface HeaderLanguages {
  /** The label of the group, for a screen reader. */
  label: string;
  options: readonly HeaderLanguage[];
  current: string;
}

export interface HeaderModel {
  name: string;
  stage: string;
  navigationLabel: string;
  links: readonly HeaderLink[];
  /** Left out until there is more than one language to choose. */
  languages?: HeaderLanguages;
}

export const LOGO_PATHS = [
  "M3 20c3-10 6-14 9-14s6 4 9 14",
  "M3 4c3 6 6 8 9 8s6-2 9-8",
] as const;

export function linkClass(current: boolean | undefined): string {
  return current === true
    ? "sb-header__link sb-header__link--current"
    : "sb-header__link";
}

export function hasLanguageChoice(
  languages: HeaderLanguages | undefined,
): languages is HeaderLanguages {
  return languages !== undefined && languages.options.length > 1;
}
