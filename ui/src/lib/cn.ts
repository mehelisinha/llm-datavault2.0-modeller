/**
 * Tiny classnames helper (Tailwind-friendly).
 *
 * Avoids pulling in `clsx` for one-line concatenation. Drops falsy values
 * so callers can write `cn("base", isActive && "active")`.
 */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
