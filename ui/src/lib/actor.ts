/**
 * Reviewer identity source.
 *
 * Phase B6 stub: returns a string from env. Phase B7 will replace this
 * with a function that pulls the verified Entra ID claim from the MSAL
 * account object. Callers should depend on `getActor()`, never on the
 * underlying source — that keeps the swap to MSAL a one-file change.
 */
import { env } from "@/env";

export function getActor(): string {
  return env.devActor;
}

/** Header name agreed with the FastAPI routers (`approvals.py`, etc.). */
export const ACTOR_HEADER = "X-Actor";
