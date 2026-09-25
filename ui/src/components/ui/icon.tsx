import { type LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

/**
 * Icon size scale.
 *
 * Pixel values live in this single map so component code never writes
 * `size={16}` inline. Adding a new size means adding a key here.
 */
export const ICON_SIZE_PX = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 20,
  xl: 24,
} as const;

export type IconSize = keyof typeof ICON_SIZE_PX;

interface IconProps {
  icon: LucideIcon;
  size?: IconSize;
  className?: string;
  "aria-label"?: string;
}

/** Thin wrapper around lucide icons that enforces the size scale. */
export function Icon({
  icon: IconComponent,
  size = "md",
  className,
  "aria-label": ariaLabel,
}: IconProps) {
  return (
    <IconComponent
      size={ICON_SIZE_PX[size]}
      className={cn("shrink-0", className)}
      aria-hidden={ariaLabel ? undefined : true}
      aria-label={ariaLabel}
      role={ariaLabel ? "img" : undefined}
    />
  );
}
