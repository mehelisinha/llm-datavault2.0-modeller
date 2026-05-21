/**
 * Renders the live queue of toasts in a fixed bottom-right stack.
 *
 * Subscribes to the framework-free store via ``useSyncExternalStore`` so
 * there is no context, no provider, and no extra render scope. Mount once
 * near the application root.
 */
export declare function Toaster(): import("react/jsx-runtime").JSX.Element | null;
