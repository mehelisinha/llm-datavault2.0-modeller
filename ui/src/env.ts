/**
 * Typed, validated env access.
 *
 * `import.meta.env` is `Record<string, string>` at runtime; we parse it
 * once with zod and re-export a frozen object so the rest of the app gets
 * proper types and clear errors when a value is missing.
 */
import { z } from "zod";

const envSchema = z.object({
  /** API base URL; empty string means "same origin" (production). */
  VITE_API_BASE_URL: z.string().default(""),
  /** Reviewer identity sent as `X-Actor` header (B6 stub; B7 swaps to JWT). */
  VITE_DEV_ACTOR: z.string().min(1).default("dev@local"),
  /** Optional defaults forwarded to discovery snapshot when set. */
  VITE_DEFAULT_SYSTEM_ID: z.string().default(""),
  VITE_DEFAULT_SYSTEM_NAME: z.string().default(""),
  VITE_DEFAULT_RECORD_SOURCE: z.string().default(""),
});

const parsed = envSchema.safeParse(import.meta.env);
if (!parsed.success) {
  // Fail loud at boot — never ship with malformed env.
  // eslint-disable-next-line no-console
  console.error("Invalid environment variables", parsed.error.format());
  throw new Error("Invalid environment variables — see console for details.");
}

export const env = Object.freeze({
  apiBaseUrl: parsed.data.VITE_API_BASE_URL,
  devActor: parsed.data.VITE_DEV_ACTOR,
  defaults: Object.freeze({
    systemId: parsed.data.VITE_DEFAULT_SYSTEM_ID,
    systemName: parsed.data.VITE_DEFAULT_SYSTEM_NAME,
    recordSource: parsed.data.VITE_DEFAULT_RECORD_SOURCE,
  }),
});

export type Env = typeof env;
