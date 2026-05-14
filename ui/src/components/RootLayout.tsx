import { Link, Outlet } from "@tanstack/react-router";

import { PRIMARY_NAV, ROUTE_LABELS } from "@/constants/routes";
import { cn } from "@/lib/cn";

/**
 * App shell: top navigation + outlet.
 *
 * Kept intentionally minimal in B6.1; the design pass (B6.2) replaces the
 * raw nav with a shadcn `NavigationMenu`.
 */
export function RootLayout() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b border-surface-muted bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
          <span className="text-lg font-semibold tracking-tight">
            DWA Metadata Generator
          </span>
          <nav className="flex gap-2 text-sm">
            {PRIMARY_NAV.map((path) => (
              <Link
                key={path}
                to={path}
                activeProps={{ className: "bg-surface-muted" }}
                className={cn(
                  "rounded px-3 py-1.5 text-slate-700 hover:bg-surface-muted",
                )}
              >
                {ROUTE_LABELS[path]}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
