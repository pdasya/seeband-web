import { Fragment, type ReactNode } from "react";

import {
  hasLanguageChoice,
  linkClass,
  LOGO_PATHS,
  type HeaderLink,
  type HeaderModel,
} from "./model";

export interface SiteHeaderProps extends HeaderModel {
  /** Draws a link, for a router. By default, a plain link. */
  renderLink?: (link: HeaderLink) => ReactNode;
  onLanguageChange?: (code: string) => void;
}

function PlainLink(link: HeaderLink) {
  return (
    <a
      href={link.href}
      className={linkClass(link.current)}
      {...(link.current === true ? { "aria-current": "page" as const } : {})}
    >
      {link.label}
    </a>
  );
}

/** The header for React. `SiteHeader.astro` draws the same markup, and a test compares them. */
export function SiteHeader({
  name,
  stage,
  navigationLabel,
  links,
  languages,
  renderLink = PlainLink,
  onLanguageChange,
}: SiteHeaderProps) {
  return (
    <header className="sb-header">
      <div className="sb-header__inner">
        <div className="sb-header__brand">
          <div className="sb-header__logo">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              {LOGO_PATHS.map((path) => (
                <path key={path} d={path} />
              ))}
            </svg>
          </div>
          <div className="sb-header__name">{name}</div>
          <span className="sb-header__stage">{stage}</span>
        </div>
        <nav aria-label={navigationLabel} className="sb-header__nav">
          {links.map((link) => (
            <Fragment key={link.id}>{renderLink(link)}</Fragment>
          ))}
        </nav>
        {hasLanguageChoice(languages) && (
          <div
            role="radiogroup"
            aria-label={languages.label}
            className="sb-header__languages"
          >
            {languages.options.map((option) => (
              <button
                key={option.code}
                type="button"
                role="radio"
                aria-checked={option.code === languages.current}
                aria-label={option.name}
                data-language={option.code}
                className="sb-header__language"
                onClick={() => onLanguageChange?.(option.code)}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </header>
  );
}
