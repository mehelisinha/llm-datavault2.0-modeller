import { jsx as _jsx } from "react/jsx-runtime";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {} from "react";
import { DwaPipelineProvider } from "@/context/DwaPipelineContext";
export function createTestWrapper() {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    return function Wrapper({ children }) {
        return (_jsx(QueryClientProvider, { client: client, children: _jsx(DwaPipelineProvider, { children: children }) }));
    };
}
