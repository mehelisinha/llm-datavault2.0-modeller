import { Badge, type BadgeIntent } from "./badge";

import { type ChangeCategory } from "@/constants/dv";

/**
 * Maps a backend `ChangeCategory` to a visually meaningful badge intent.
 *
 * The `Record` type forces the table to stay total: adding a new category
 * to `CHANGE_CATEGORIES` will fail the typecheck until a render decision is
 * made here. Components must never branch on category strings directly.
 */
const CHANGE_CATEGORY_INTENT: Readonly<Record<ChangeCategory, BadgeIntent>> = {
  NEW: "success",
  SCHEMA_CHANGED: "warning",
  UNCHANGED: "neutral",
  ORPHANED: "destructive",
};

interface StatusPillProps {
  category: ChangeCategory;
  className?: string;
}

/** Domain-aware pill rendering a `ChangeCategory` consistently across the app. */
export function StatusPill({ category, className }: StatusPillProps) {
  return (
    <Badge intent={CHANGE_CATEGORY_INTENT[category]} className={className}>
      {category}
    </Badge>
  );
}
