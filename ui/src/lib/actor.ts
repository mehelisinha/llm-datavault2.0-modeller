/**
 * Reviewer identity source.
 *
 * The display-name resolver is wired by `ActorBridge` once `AuthProvider`
 * has mounted. While MSAL is unconfigured (dev mode) the resolver remains
 * `null` and we fall back to `VITE_DEV_ACTOR`. Callers always depend on
 * `getActor()` so the swap is invisible to them.
 */
import { env } from "@/env";

let displayNameResolver: (() => string) | null = null;

export function setDisplayNameResolver(resolver: () => string): void {
  displayNameResolver = resolver;
}

export function getActor(): string {
  if (displayNameResolver) {
    const resolved = displayNameResolver();
    if (resolved && resolved.trim()) {
      return resolved.trim();
    }
  }
  return env.devActor;
}

/** Header name agreed with the FastAPI routers (`approvals.py`, etc.). */
export const ACTOR_HEADER = "X-Actor";
