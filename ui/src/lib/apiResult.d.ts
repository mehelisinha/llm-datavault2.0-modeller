/**
 * Unwrap an openapi-fetch result, throwing on HTTP or client errors.
 *
 * openapi-fetch puts the parsed response body into `result.error` for non-2xx
 * responses. That body is a plain object (e.g. `{ detail: "..." }` from
 * FastAPI's 422/503 responses), NOT an Error instance. We convert it here so
 * every `mutation.error` in the UI is always a real `Error` with a readable
 * `.message`, preventing the infamous "[object Object]" display.
 */
export declare function unwrapApiResult<T>(result: {
    data?: T;
    error?: unknown;
}): T;
