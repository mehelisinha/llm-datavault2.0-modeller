import { cva, type VariantProps } from "class-variance-authority";
import {
  type ButtonHTMLAttributes,
  forwardRef,
  type ReactNode,
} from "react";

import { cn } from "@/lib/cn";

/**
 * Variant catalogue for the `Button` primitive.
 *
 * Exposed via `VariantProps` so callers cannot pass undeclared values.
 * All visual choices live here so application code never repeats colour /
 * spacing / radius utilities.
 */
const buttonVariants = cva(
  cn(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium",
    "transition-all duration-150 active:scale-[0.98]",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    "disabled:pointer-events-none disabled:opacity-50",
  ),
  {
    variants: {
      intent: {
        primary: "bg-primary text-primary-foreground shadow-xs hover:bg-primary/90 hover:shadow-sm",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        outline:
          "border border-input bg-background shadow-xs hover:bg-accent hover:text-accent-foreground",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        destructive:
          "bg-destructive text-destructive-foreground shadow-xs hover:bg-destructive/90",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-9 px-4",
        lg: "h-10 px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      intent: "primary",
      size: "md",
    },
  },
);

export type ButtonIntent = NonNullable<VariantProps<typeof buttonVariants>["intent"]>;
export type ButtonSize = NonNullable<VariantProps<typeof buttonVariants>["size"]>;

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, intent, size, leftIcon, rightIcon, children, type, ...rest }, ref) => (
    <button
      ref={ref}
      // Default to type="button" so a misplaced button never accidentally
      // submits an enclosing form. Callers opt into "submit" explicitly.
      type={type ?? "button"}
      className={cn(buttonVariants({ intent, size }), className)}
      {...rest}
    >
      {leftIcon ? <span className="-ml-0.5">{leftIcon}</span> : null}
      {children}
      {rightIcon ? <span className="-mr-0.5">{rightIcon}</span> : null}
    </button>
  ),
);
Button.displayName = "Button";

export { buttonVariants };
