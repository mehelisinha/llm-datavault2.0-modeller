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

// TODO(B6.3): swap `unknown` for `import("./schema").paths` after first
// `pnpm gen:api` run against the running FastAPI instance.
type Paths = Record<string, unknown>;

const actorMiddleware: Middleware = {
  onRequest({ request }) {
    request.headers.set(ACTOR_HEADER, getActor());
    return request;
  },
};

export const api = createClient<Paths>({
  baseUrl: env.apiBaseUrl,
});

api.use(actorMiddleware);
