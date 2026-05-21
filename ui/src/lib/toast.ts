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
export const TOAST_LIFETIME_MS = 4500;

/** Mapping from toast intent to the matching button colour token. */
export const TOAST_INTENT_TO_BUTTON: Readonly<Record<ToastIntent, ButtonIntent>> = Object.freeze({
  success: "primary",
  error: "destructive",
  info: "secondary",
  warning: "outline",
});

type Listener = () => void;

const listeners = new Set<Listener>();
let toasts: ReadonlyArray<ToastRecord> = [];
let nextId = 0;

function emit(): void {
  for (const listener of listeners) listener();
}

export function getToasts(): ReadonlyArray<ToastRecord> {
  return toasts;
}

export function subscribeToToasts(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function dismissToast(id: string): void {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

function push(intent: ToastIntent, title: string, description?: string): string {
  nextId += 1;
  const id = String(nextId);
  const record: ToastRecord = description ? { id, intent, title, description } : { id, intent, title };
  toasts = [...toasts, record];
  emit();
  if (typeof window !== "undefined") {
    window.setTimeout(() => dismissToast(id), TOAST_LIFETIME_MS);
  }
  return id;
}

/**
 * Imperative toast API.
 *
 * Designed to be callable from React Query `onSuccess` / `onError` callbacks
 * without needing a hook — keeping the call sites short.
 */
export const toast = Object.freeze({
  success(title: string, description?: string): string {
    return push("success", title, description);
  },
  error(title: string, description?: string): string {
    return push("error", title, description);
  },
  info(title: string, description?: string): string {
    return push("info", title, description);
  },
  warning(title: string, description?: string): string {
    return push("warning", title, description);
  },
  dismiss: dismissToast,
});

/** Test-only helper to wipe the queue between specs. Never call from app code. */
export function _resetToastStoreForTests(): void {
  toasts = [];
  nextId = 0;
}
