import { SiteHeader } from "@seeband/ui/SiteHeader";
import { linkClass } from "@seeband/ui/header-model";
import { NavLink } from "react-router";

import { STRINGS } from "@/strings";

// The overview belongs to the public site at /, so it leaves the app's router. The site has the
// same sections; Conventions joins both when its page exists (S3).
const SITE_LINKS = new Set(["overview"]);

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
