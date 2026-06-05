import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter } from "@tanstack/react-router";

import { queryClient } from "@/api/queryClient";
import { AuthProvider } from "@/auth/AuthProvider";
import { ActorBridge } from "@/components/ActorBridge";
import { DwaPipelineProvider } from "@/context/DwaPipelineContext";
import { Toaster } from "@/components/ui/toaster";
import { routeTree } from "@/routes";

import "./app.css";

const router = createRouter({ routeTree, defaultPreload: "intent" });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found in index.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ActorBridge />
        <DwaPipelineProvider>
          <RouterProvider router={router} />
          <Toaster />
        </DwaPipelineProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
