/**
 * Typed, validated env access.
 *
 * `import.meta.env` is `Record<string, string>` at runtime; we parse it
 * once with zod and re-export a frozen object so the rest of the app gets
 * proper types and clear errors when a value is missing.
 *
 * MSAL is OPT-IN: when `VITE_MSAL_CLIENT_ID` + `VITE_MSAL_TENANT_ID` are
 * unset the UI runs in dev mode and identifies the reviewer via
 * `VITE_DEV_ACTOR`.
 */
import { z } from "zod";

const envSchema = z.object({
  /** API base URL; empty string means "same origin" (production). */
  VITE_API_BASE_URL: z.string().default(""),
  /** Reviewer identity sent as `X-Actor` header when MSAL is not configured. */
  VITE_DEV_ACTOR: z.string().min(1).default("dev@local"),
  /** Optional defaults forwarded to discovery snapshot when set. */
  VITE_DEFAULT_SYSTEM_ID: z.string().default(""),
  VITE_DEFAULT_SYSTEM_NAME: z.string().default(""),
  VITE_DEFAULT_RECORD_SOURCE: z.string().default(""),
  /** Optional defaults that pre-populate the Discovery form on first load. */
  VITE_DEFAULT_CATALOG: z.string().default(""),
  VITE_DEFAULT_BRONZE_SCHEMA: z.string().default(""),
  VITE_DEFAULT_VAULT_SCHEMA: z.string().default(""),
  /** Microsoft Entra ID (MSAL) — opt-in. */
  VITE_MSAL_CLIENT_ID: z.string().default(""),
  VITE_MSAL_TENANT_ID: z.string().default(""),
  VITE_MSAL_AUTHORITY: z.string().default(""),
  VITE_MSAL_REDIRECT_URI: z.string().default(""),
  VITE_MSAL_API_SCOPE: z.string().default(""),
  /** Branding shown on the login page. */
  VITE_APP_NAME: z.string().default("DWA Metadata Generator"),
  VITE_APP_TENANT_NAME: z.string().default("ExampleCorp"),
});

const parsed = envSchema.safeParse(import.meta.env);
if (!parsed.success) {
  // Fail loud at boot — never ship with malformed env.
  // eslint-disable-next-line no-console
  console.error("Invalid environment variables", parsed.error.format());
  throw new Error("Invalid environment variables — see console for details.");
}

const tenantId = parsed.data.VITE_MSAL_TENANT_ID;
const authority =
  parsed.data.VITE_MSAL_AUTHORITY ||
  (tenantId ? `https://login.microsoftonline.com/${tenantId}` : "");
const redirectUri =
  parsed.data.VITE_MSAL_REDIRECT_URI ||
  (typeof window !== "undefined" ? window.location.origin : "");

export const env = Object.freeze({
  apiBaseUrl: parsed.data.VITE_API_BASE_URL,
  devActor: parsed.data.VITE_DEV_ACTOR,
  appName: parsed.data.VITE_APP_NAME,
  tenantName: parsed.data.VITE_APP_TENANT_NAME,
  defaults: Object.freeze({
    systemId: parsed.data.VITE_DEFAULT_SYSTEM_ID,
    systemName: parsed.data.VITE_DEFAULT_SYSTEM_NAME,
    recordSource: parsed.data.VITE_DEFAULT_RECORD_SOURCE,
    catalog: parsed.data.VITE_DEFAULT_CATALOG,
    bronzeSchema: parsed.data.VITE_DEFAULT_BRONZE_SCHEMA,
    vaultSchema: parsed.data.VITE_DEFAULT_VAULT_SCHEMA,
  }),
  msal: Object.freeze({
    clientId: parsed.data.VITE_MSAL_CLIENT_ID,
    tenantId,
    authority,
    redirectUri,
    apiScope: parsed.data.VITE_MSAL_API_SCOPE,
  }),
});

export type Env = typeof env;
