/**
 * Framework-free toast store.
 *
 * Why home-grown rather than sonner / radix-toast: zero new deps, single
 * source of truth for intents/lifetimes, and the codebase already follows
 * a "small primitive in-repo" pattern (Button, Card, StatusPill, ...).
 *
 * The store uses the subscribe / getSnapshot pattern that React 18's
 * ``useSyncExternalStore`` is designed for — so the ``<Toaster />`` does
 * not even need a Context or a hook to subscribe.
 */
import type { ButtonIntent } from "@/components/ui";
export type ToastIntent = "success" | "error" | "info" | "warning";
export interface ToastRecord {
    readonly id: string;
    readonly intent: ToastIntent;
    readonly title: string;
    readonly description?: string;
}
/** How long, in milliseconds, a toast stays visible before auto-dismissing. */
export declare const TOAST_LIFETIME_MS = 4500;
/** Mapping from toast intent to the matching button colour token. */
export declare const TOAST_INTENT_TO_BUTTON: Readonly<Record<ToastIntent, ButtonIntent>>;
type Listener = () => void;
export declare function getToasts(): ReadonlyArray<ToastRecord>;
export declare function subscribeToToasts(listener: Listener): () => void;
export declare function dismissToast(id: string): void;
/**
 * Imperative toast API.
 *
 * Designed to be callable from React Query `onSuccess` / `onError` callbacks
 * without needing a hook — keeping the call sites short.
 */
export declare const toast: Readonly<{
    success(title: string, description?: string): string;
    error(title: string, description?: string): string;
    info(title: string, description?: string): string;
    warning(title: string, description?: string): string;
    dismiss: typeof dismissToast;
}>;
/** Test-only helper to wipe the queue between specs. Never call from app code. */
export declare function _resetToastStoreForTests(): void;
export {};
