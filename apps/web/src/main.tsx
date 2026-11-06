import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";

import "@/index.css";
import { ROUTES } from "@/routes";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("The page has no root element");
}
const router = createBrowserRouter(ROUTES, {
  basename: import.meta.env.BASE_URL,
});
createRoot(root).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
