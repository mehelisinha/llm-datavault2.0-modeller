/**
 * Unwrap an openapi-fetch result, throwing on HTTP or client errors.
 *
 * openapi-fetch puts the parsed response body into `result.error` for non-2xx
 * responses. That body is a plain object (e.g. `{ detail: "..." }` from
 * FastAPI's 422/503 responses), NOT an Error instance. We convert it here so
 * every `mutation.error` in the UI is always a real `Error` with a readable
 * `.message`, preventing the infamous "[object Object]" display.
 */
export function unwrapApiResult<T>(result: { data?: T; error?: unknown }): T {
  if (result.error !== undefined && result.error !== null) {
    if (result.error instanceof Error) {
      throw result.error;
    }
    // FastAPI error bodies are { detail: string | array }
    const raw = result.error as Record<string, unknown>;
    let message: string;
    if (typeof raw["detail"] === "string") {
      message = raw["detail"];
    } else if (Array.isArray(raw["detail"])) {
      // Pydantic 422 validation errors: [{ loc, msg, type }]
      message = (raw["detail"] as Array<{ msg?: string }>)
        .map((e) => e.msg ?? JSON.stringify(e))
        .join("; ");
    } else {
      message = JSON.stringify(result.error);
    }
    throw new Error(message);
  }
  if (result.data === undefined) {
    throw new Error("API response missing data");
  }
  return result.data;
}
