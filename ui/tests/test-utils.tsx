import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";

import { AuthProvider } from "@/auth/AuthProvider";
import { DwaPipelineProvider } from "@/context/DwaPipelineContext";

export function createTestWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <AuthProvider>
          <DwaPipelineProvider>{children}</DwaPipelineProvider>
        </AuthProvider>
      </QueryClientProvider>
    );
  };
}
