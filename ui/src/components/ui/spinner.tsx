import { Loader2 } from "lucide-react";

import { cn } from "@/lib/cn";

import { ICON_SIZE_PX, type IconSize } from "./icon";

interface SpinnerProps {
  size?: IconSize;
  className?: string;
  label?: string;
}

/** Accessible loading indicator. The visually hidden label feeds screen readers. */
export function Spinner({ size = "md", className, label = "Loading" }: SpinnerProps) {
  return (
    <span role="status" className={cn("inline-flex items-center", className)}>
      <Loader2
        size={ICON_SIZE_PX[size]}
        className="animate-spin text-muted-foreground"
        aria-hidden="true"
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
