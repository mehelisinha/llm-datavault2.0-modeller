import type { ReactNode } from "react";

interface PageShellProps {
  title: string;
  description?: string;
  children?: ReactNode;
  actions?: ReactNode;
}

/**
 * Standard page chrome.
 *
 * Centralised so every route renders the same heading rhythm, spacing, and
 * actions slot. Pages must never re-implement the title/description markup.
 */
export function PageShell({ title, description, children, actions }: PageShellProps) {
  return (
    <section className="space-y-6 animate-fade-in">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          {description ? (
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </header>
      <div>{children}</div>
    </section>
  );
}

