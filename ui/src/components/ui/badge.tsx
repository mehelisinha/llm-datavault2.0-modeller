import { cva, type VariantProps } from "class-variance-authority";
import { type HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

/**
 * Compact status / label pill.
 *
 * `intent` mirrors the semantic colour tokens so consumers express meaning
 * (`success`, `warning`) rather than colour. Keep variant strings in sync
 * with `StatusPill` so we never invent ad-hoc styles for the same idea.
 */
const badgeVariants = cva(
  cn(
    "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
    "transition-colors focus:outline-none focus:ring-2 focus:ring-ring",
  ),
  {
    variants: {
      intent: {
        neutral: "border-transparent bg-secondary text-secondary-foreground",
        primary: "border-transparent bg-primary text-primary-foreground",
        success: "border-transparent bg-success text-success-foreground",
        warning: "border-transparent bg-warning text-warning-foreground",
        destructive: "border-transparent bg-destructive text-destructive-foreground",
        info: "border-transparent bg-info text-info-foreground",
        outline: "text-foreground",
      },
    },
    defaultVariants: {
      intent: "neutral",
    },
  },
);

export type BadgeIntent = NonNullable<VariantProps<typeof badgeVariants>["intent"]>;

interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, intent, ...rest }: BadgeProps) {
  return <span className={cn(badgeVariants({ intent }), className)} {...rest} />;
}

export { badgeVariants };
