/**
 * Singleton TanStack Query client.
 *
 * Defaults are tuned for an internal review tool:
 * - `staleTime: 30s` — most reads (history, diff) are cheap to refetch but
 *   we don't want a re-fetch storm on every focus change.
 * - `retry: 1` — fail fast; the user can hit retry manually.
 * - `refetchOnWindowFocus: false` — review screens shouldn't reshuffle
 *   underneath the reviewer.
 */
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
