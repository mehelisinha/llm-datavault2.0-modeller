import { type VariantProps } from "class-variance-authority";
import { type HTMLAttributes } from "react";
/**
 * Compact status / label pill.
 *
 * `intent` mirrors the semantic colour tokens so consumers express meaning
 * (`success`, `warning`) rather than colour. Keep variant strings in sync
 * with `StatusPill` so we never invent ad-hoc styles for the same idea.
 */
declare const badgeVariants: (props?: ({
    intent?: "success" | "primary" | "outline" | "destructive" | "warning" | "info" | "neutral" | null | undefined;
} & import("class-variance-authority/types").ClassProp) | undefined) => string;
export type BadgeIntent = NonNullable<VariantProps<typeof badgeVariants>["intent"]>;
interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {
}
export declare function Badge({ className, intent, ...rest }: BadgeProps): import("react/jsx-runtime").JSX.Element;
export { badgeVariants };
