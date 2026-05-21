import { Badge, type BadgeIntent } from "./badge";

import {
  CHANGE_CATEGORY_INTENTS,
  CHANGE_CATEGORY_LABELS,
  type ChangeCategory,
} from "@/constants/dv";

interface StatusPillProps {
  category: ChangeCategory;
  className?: string;
}

/**
 * Domain-aware pill rendering a `ChangeCategory` consistently across the app.
 *
 * Both the intent (color) and the display label come from the generated
 * `dv.ts` constants, which mirror the Python source of truth. Components
 * must never branch on category strings directly.
 */
export function StatusPill({ category, className }: StatusPillProps) {
  const intent = CHANGE_CATEGORY_INTENTS[category] as BadgeIntent | undefined;
  return (
    <Badge intent={intent} className={className}>
      {CHANGE_CATEGORY_LABELS[category]}
    </Badge>
  );
}
