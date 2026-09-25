import { type HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

interface SeparatorProps extends HTMLAttributes<HTMLDivElement> {
  orientation?: "horizontal" | "vertical";
}

const ORIENTATION_CLASSES = {
  horizontal: "h-px w-full",
  vertical: "h-full w-px",
} as const satisfies Record<NonNullable<SeparatorProps["orientation"]>, string>;

/** Theme-aware divider that adapts to layout direction. */
export function Separator({
  className,
  orientation = "horizontal",
  ...rest
}: SeparatorProps) {
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      className={cn("shrink-0 bg-border", ORIENTATION_CLASSES[orientation], className)}
      {...rest}
    />
  );
}
