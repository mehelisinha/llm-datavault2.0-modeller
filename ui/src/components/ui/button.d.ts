import { type VariantProps } from "class-variance-authority";
import { type ButtonHTMLAttributes, type ReactNode } from "react";
/**
 * Variant catalogue for the `Button` primitive.
 *
 * Exposed via `VariantProps` so callers cannot pass undeclared values.
 * All visual choices live here so application code never repeats colour /
 * spacing / radius utilities.
 */
declare const buttonVariants: (props?: ({
    intent?: "link" | "primary" | "secondary" | "outline" | "ghost" | "destructive" | null | undefined;
    size?: "sm" | "md" | "lg" | "icon" | null | undefined;
} & import("class-variance-authority/types").ClassProp) | undefined) => string;
export type ButtonIntent = NonNullable<VariantProps<typeof buttonVariants>["intent"]>;
export type ButtonSize = NonNullable<VariantProps<typeof buttonVariants>["size"]>;
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
    leftIcon?: ReactNode;
    rightIcon?: ReactNode;
}
export declare const Button: import("react").ForwardRefExoticComponent<ButtonProps & import("react").RefAttributes<HTMLButtonElement>>;
export { buttonVariants };
