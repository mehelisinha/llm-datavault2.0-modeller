import { useSyncExternalStore } from "react";
import { CheckCircle2, Info, AlertTriangle, XCircle, X } from "lucide-react";

import { cn } from "../../lib/cn";
import {
  dismissToast,
  getToasts,
  subscribeToToasts,
  type ToastIntent,
} from "../../lib/toast";

/**
 * Visual styling per toast intent.
 *
 * Centralised here so call sites stay token-free: they only pick a semantic
 * intent (``success`` / ``error`` / ``info`` / ``warning``), never a colour.
 */
const INTENT_CLASSES: Readonly<Record<ToastIntent, string>> = Object.freeze({
  success: "border-success/40 bg-success/10 text-foreground",
  error: "border-destructive/40 bg-destructive/10 text-foreground",
  info: "border-info/40 bg-info/10 text-foreground",
  warning: "border-warning/40 bg-warning/10 text-foreground",
});

const INTENT_ICON: Readonly<Record<ToastIntent, typeof CheckCircle2>> = Object.freeze({
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
});

const INTENT_ICON_CLASS: Readonly<Record<ToastIntent, string>> = Object.freeze({
  success: "text-success",
  error: "text-destructive",
  info: "text-info",
  warning: "text-warning",
});

/**
 * Renders the live queue of toasts in a fixed bottom-right stack.
 *
 * Subscribes to the framework-free store via ``useSyncExternalStore`` so
 * there is no context, no provider, and no extra render scope. Mount once
 * near the application root.
 */
export function Toaster() {
  const toasts = useSyncExternalStore(subscribeToToasts, getToasts, getToasts);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      aria-atomic="true"
      className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2"
    >
      {toasts.map((t) => {
        const IconComponent = INTENT_ICON[t.intent];
        return (
          <div
            key={t.id}
            role="status"
            className={cn(
              "pointer-events-auto flex items-start gap-3 rounded-md border bg-card p-3 shadow-md animate-fade-in",
              INTENT_CLASSES[t.intent],
            )}
          >
            <IconComponent
              aria-hidden="true"
              className={cn("mt-0.5 h-5 w-5 flex-shrink-0", INTENT_ICON_CLASS[t.intent])}
            />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold leading-tight">{t.title}</p>
              {t.description ? (
                <p className="mt-1 break-words text-xs text-muted-foreground">{t.description}</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => dismissToast(t.id)}
              className="rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Dismiss notification"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
