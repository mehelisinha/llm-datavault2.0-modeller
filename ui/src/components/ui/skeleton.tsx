import { type HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

/**
 * Animated placeholder block. Use during data loading instead of empty
 * containers so layout stays stable.
 */
export function Skeleton({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted", className)}
      aria-hidden="true"
      {...rest}
    />
  );
}
