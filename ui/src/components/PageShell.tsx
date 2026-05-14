import type { ReactNode } from "react";

interface PageShellProps {
  title: string;
  description?: string;
  children?: ReactNode;
  actions?: ReactNode;
}

/**
 * Standard page chrome. Centralised so every page has the same heading
 * rhythm and we never re-implement title/description markup per route.
 */
export function PageShell({ title, description, children, actions }: PageShellProps) {
  return (
    <section className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {description ? (
            <p className="mt-1 text-sm text-slate-600">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </header>
      <div>{children}</div>
    </section>
  );
}
