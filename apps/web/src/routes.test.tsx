import { act, cleanup, render, screen, within } from "@testing-library/react";
import {
  createMemoryRouter,
  RouterProvider,
  type RouteObject,
} from "react-router";
import { afterEach, expect, test, vi } from "vitest";

import { AppShell } from "@/shell/AppShell";
import { PageErrorView, ShellErrorView } from "@/pages/messages";
import { ROUTES } from "@/routes";
import { StatusBadge, type FitStatus } from "@/shell/StatusBadge";
import { STRINGS } from "@/strings";

afterEach(cleanup);

function renderAt(path: string, routes: RouteObject[] = ROUTES) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<RouterProvider router={router} />);
  return router;
}

function currentLink() {
  const nav = screen.getByRole("navigation", {
    name: STRINGS.navigation.label,
  });
  return within(nav)
    .getAllByRole("link")
    .filter((link) => link.getAttribute("aria-current") === "page")
    .map((link) => link.textContent);
}

test("the root leads to the fit page", () => {
  const router = renderAt("/");

  expect(router.state.location.pathname).toBe("/fit");
  expect(
    screen.getByRole("heading", { level: 1, name: STRINGS.fit.title }),
  ).toBeTruthy();
});

test.each([
  ["/fit", STRINGS.navigation.fit, STRINGS.fit.title],
  ["/results", STRINGS.navigation.results, STRINGS.results.title],
])("%s has its heading and marks its link", (path, link, heading) => {
  renderAt(path);

  expect(screen.getByRole("heading", { level: 1, name: heading })).toBeTruthy();
  expect(currentLink()).toEqual([link]);
});

test("links to the public site leave the app's router", () => {
  renderAt("/fit");

  const overview = screen.getByRole("link", {
    name: STRINGS.navigation.overview,
  });
  const conventions = screen.getByRole("link", {
    name: STRINGS.navigation.conventions,
  });
  expect(overview.getAttribute("href")).toBe("/");
  expect(conventions.getAttribute("href")).toBe("/conventions/");
});

test("an unknown path has the not-found view inside the shell", () => {
  renderAt("/nothing");

  expect(
    screen.getByRole("heading", { level: 1, name: STRINGS.notFound.title }),
  ).toBeTruthy();
  expect(screen.getByRole("navigation")).toBeTruthy();
  expect(
    screen
      .getByRole("link", { name: STRINGS.notFound.action })
      .getAttribute("href"),
  ).toBe("/fit");
});

test("the first thing to focus skips to the content", () => {
  renderAt("/fit");

  const skip = screen.getByRole("link", { name: STRINGS.skipToContent });
  const main = screen.getByRole("main");
  expect(document.body.querySelector("a")).toBe(skip);
  expect(skip.getAttribute("href")).toBe(`#${main.id}`);
});

function Broken(): never {
  throw new Error("SECRET-VALUE");
}

function expectErrorViewWithNoDetails() {
  expect(
    screen.getByRole("heading", { level: 1, name: STRINGS.error.title }),
  ).toBeTruthy();
  expect(
    screen.getByRole("button", { name: STRINGS.error.action }),
  ).toBeTruthy();
  expect(document.body.textContent).not.toContain("SECRET-VALUE");
}

test("a page that throws shows the error view inside the shell", () => {
  const silence = vi
    .spyOn(console, "error")
    .mockImplementation(() => undefined);

  renderAt("/", [
    {
      element: <AppShell />,
      errorElement: <ShellErrorView />,
      children: [
        {
          errorElement: <PageErrorView />,
          children: [{ index: true, element: <Broken /> }],
        },
      ],
    },
  ]);
  silence.mockRestore();

  expectErrorViewWithNoDetails();
  expect(screen.getByRole("navigation")).toBeTruthy();
});

test("a shell that throws still shows the error view", () => {
  const silence = vi
    .spyOn(console, "error")
    .mockImplementation(() => undefined);

  renderAt("/", [
    {
      element: <Broken />,
      errorElement: <ShellErrorView />,
      children: [
        {
          errorElement: <PageErrorView />,
          children: [{ index: true, element: null }],
        },
      ],
    },
  ]);
  silence.mockRestore();

  expectErrorViewWithNoDetails();
  expect(screen.queryByRole("navigation")).toBeNull();
});

test("the routes of the app use both error views", () => {
  const [shell] = ROUTES;
  const [pages] = shell?.children ?? [];

  expect(shell?.errorElement).toBeTruthy();
  expect(pages?.errorElement).toBeTruthy();
  expect(shell?.errorElement).not.toEqual(pages?.errorElement);
});

test("a move inside the app takes focus to the content, and the first page leaves it alone", async () => {
  const router = renderAt("/fit");
  const main = screen.getByRole("main");
  expect(document.activeElement).not.toBe(main);

  await act(() => router.navigate("/results"));

  expect(document.activeElement).toBe(main);
  expect(
    screen.getByRole("heading", { level: 1, name: STRINGS.results.title }),
  ).toBeTruthy();
});

test.each(Object.keys(STRINGS.status) as FitStatus[])(
  "status %s has its text",
  (status) => {
    render(<StatusBadge status={status} detail="7" />);

    expect(screen.getByText(`${STRINGS.status[status]} 7`)).toBeTruthy();
  },
);
