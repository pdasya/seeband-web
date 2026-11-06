import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";

import { createQueryClient } from "@/api/queries";
import "@/index.css";
import { ROUTES } from "@/routes";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("The page has no root element");
}
const router = createBrowserRouter(ROUTES);
createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={createQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
