/**
 * Access token resolver for API middleware (MSAL when configured).
 */
import { env } from "@/env";

let tokenResolver: (() => Promise<string | null>) | null = null;

export function setAccessTokenResolver(resolver: () => Promise<string | null>): void {
  tokenResolver = resolver;
}

export async function getAccessToken(): Promise<string | null> {
  if (!env.msal.clientId) {
    return null;
  }
  if (!tokenResolver) {
    return null;
  }
  return tokenResolver();
}
