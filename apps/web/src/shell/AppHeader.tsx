import { SiteHeader } from "@seeband/ui/SiteHeader";
import { linkClass } from "@seeband/ui/header-model";
import { NavLink } from "react-router";

import { STRINGS } from "@/strings";

// Overview and Conventions belong to the public site, so they leave the app's router.
const SITE_LINKS = new Set(["overview", "conventions"]);

/** The shared header, with the app's links going through its router. */
export function AppHeader() {
  const { navigation } = STRINGS;
  return (
    <SiteHeader
      name={STRINGS.appName}
      stage={STRINGS.appStage}
      navigationLabel={navigation.label}
      links={[
        { id: "overview", label: navigation.overview, href: "/" },
        { id: "fit", label: navigation.fit, href: "/fit" },
        { id: "results", label: navigation.results, href: "/results" },
        {
          id: "conventions",
          label: navigation.conventions,
          href: "/conventions/",
        },
      ]}
      renderLink={(link) =>
        SITE_LINKS.has(link.id) ? (
          <a href={link.href} className={linkClass(false)}>
            {link.label}
          </a>
        ) : (
          <NavLink
            to={link.href}
            className={({ isActive }) => linkClass(isActive)}
          >
            {link.label}
          </NavLink>
        )
      }
    />
  );
}
