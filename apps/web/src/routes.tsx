import { Navigate, type RouteObject } from "react-router";

import { FitPage } from "@/pages/FitPage";
import { ErrorPage, NotFoundPage } from "@/pages/messages";
import { ResultsPage } from "@/pages/ResultsPage";
import { AppShell } from "@/shell/AppShell";

export const ROUTES: RouteObject[] = [
  {
    element: <AppShell />,
    errorElement: <ErrorPage />,
    children: [
      { index: true, element: <Navigate to="/fit" replace /> },
      { path: "fit", element: <FitPage /> },
      { path: "results", element: <ResultsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
