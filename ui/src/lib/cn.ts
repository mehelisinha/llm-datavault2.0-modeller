import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Conditional classname helper that resolves Tailwind utility conflicts.
 *
 * Combines `clsx` (truthy filtering, array / object inputs) with
 * `tailwind-merge` (last-wins resolution for conflicting utilities like
 * `p-2` vs `p-4`). This is the shadcn/ui convention and the only sanctioned
 * way to compose class strings inside primitives.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
