/**
 * Human-readable duration formatting.
 *
 * Agent/step timings arrive from the backend in milliseconds, which is
 * unreadable past a second or two. This promotes the unit as the magnitude
 * grows: milliseconds → seconds (≥ 1s) → minutes (≥ 1min). Used everywhere a
 * duration is shown so the rule lives in exactly one place.
 */

export const MS_PER_SECOND = 1_000;
export const SECONDS_PER_MINUTE = 60;
export const MS_PER_MINUTE = MS_PER_SECOND * SECONDS_PER_MINUTE;

/** Largest number of fractional digits shown on a promoted (s/min) value. */
const MAX_FRACTION_DIGITS = 1;

function compact(value: number): string {
  // One decimal place, but drop a trailing ".0" so "2.0 s" reads as "2 s".
  return value
    .toFixed(MAX_FRACTION_DIGITS)
    .replace(/\.0+$/, "");
}

/**
 * Format a millisecond duration with an automatically chosen unit.
 *
 * @example formatDuration(850)   // "850 ms"
 * @example formatDuration(1500)  // "1.5 s"
 * @example formatDuration(90000) // "1.5 min"
 */
export function formatDuration(ms: number): string {
  if (typeof ms !== "number" || !Number.isFinite(ms) || ms < 0) {
    return "—";
  }
  if (ms >= MS_PER_MINUTE) {
    return `${compact(ms / MS_PER_MINUTE)} min`;
  }
  if (ms >= MS_PER_SECOND) {
    return `${compact(ms / MS_PER_SECOND)} s`;
  }
  return `${Math.round(ms)} ms`;
}
