/**
 * HTTP client.
 *
 * Wraps `openapi-fetch` with two cross-cutting concerns:
 *
 * 1. Base URL from typed env — no hardcoded literals.
 * 2. Actor header — added to every request via middleware. Phase B7 swaps
 *    this for an Entra ID Bearer token.
 *
 * Once `pnpm gen:api` has produced `src/api/schema.d.ts`, replace the
 * `unknown` paths type with `import("./schema").paths` for full
 * end-to-end type safety against the FastAPI OpenAPI document.
 */
import createClient, { type Middleware } from "openapi-fetch";

import { env } from "@/env";
import { ACTOR_HEADER, getActor } from "@/lib/actor";
import { getAccessToken } from "@/lib/authToken";

// TODO(B6.3): swap `unknown` for `import("./schema").paths` after first
// `pnpm gen:api` run against the running FastAPI instance.
type Paths = Record<string, unknown>;

/**
 * Attach reviewer identity to every request.
 *
 * Two parallel mechanisms cover both auth modes without per-call branching:
 *  - `Authorization: Bearer <token>` from MSAL when configured.
 *  - `X-Actor: <email>` fallback for dev mode (and for any endpoint that
 *    has not yet been migrated to JWT-only).
 * The backend prefers the bearer token when present.
 */
const authMiddleware: Middleware = {
  async onRequest({ request }) {
    request.headers.set(ACTOR_HEADER, getActor());
    const token = await getAccessToken();
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    return request;
  },
};

export const api = createClient<Paths>({
  baseUrl: env.apiBaseUrl,
});

api.use(authMiddleware);
