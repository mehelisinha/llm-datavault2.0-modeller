import { Link, Outlet } from "@tanstack/react-router";
import { Database } from "lucide-react";

import { Icon } from "@/components/ui";
import { ADVANCED_NAV, PRIMARY_NAV, ROUTE_LABELS, WORKFLOW_LABELS } from "@/constants/routes";
import { cn } from "@/lib/cn";

const SHELL_MAX_WIDTH = "max-w-6xl";

/**
 * App shell: top navigation + outlet.
 *
 * The header consumes only semantic theme tokens so dark-mode and rebrands
 * land via CSS variables alone. `SHELL_MAX_WIDTH` is the single source of
 * truth for content width.
 */
export function RootLayout() {
  return (
    <div className="flex min-h-full flex-col bg-background text-foreground">
      <header className="border-b border-border bg-card/80 backdrop-blur supports-[backdrop-filter]:bg-card/60">
        <div
          className={cn(
            "mx-auto flex items-center gap-6 px-6 py-3",
            SHELL_MAX_WIDTH,
          )}
        >
          <span className="flex items-center gap-2 text-base font-semibold tracking-tight">
            <Icon icon={Database} size="lg" className="text-primary" />
            DWA Metadata Generator
          </span>
          <div className="flex flex-1 flex-wrap items-center gap-x-4 gap-y-1">
            <nav className="flex gap-1 text-sm" aria-label="Primary">
              {PRIMARY_NAV.map((path) => (
                <Link
                  key={path}
                  to={path}
                  activeProps={{
                    className: "bg-secondary text-secondary-foreground",
                  }}
                  inactiveProps={{
                    className: "text-muted-foreground hover:text-foreground",
                  }}
                  className={cn(
                    "rounded-md px-3 py-1.5 transition-colors hover:bg-secondary",
                  )}
                >
                  {ROUTE_LABELS[path]}
                </Link>
              ))}
            </nav>
            <nav
              className="flex items-center gap-1 text-sm"
              aria-label={WORKFLOW_LABELS.advancedNavGroup}
            >
              <span className="px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {WORKFLOW_LABELS.advancedNavGroup}
              </span>
              {ADVANCED_NAV.map((path) => (
                <Link
                  key={path}
                  to={path}
                  activeProps={{
                    className: "bg-muted text-foreground",
                  }}
                  inactiveProps={{
                    className: "text-muted-foreground hover:text-foreground",
                  }}
                  className={cn(
                    "rounded-md px-2.5 py-1 transition-colors hover:bg-muted",
                  )}
                >
                  {ROUTE_LABELS[path]}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </header>
      <main
        className={cn("mx-auto w-full flex-1 px-6 py-8", SHELL_MAX_WIDTH)}
      >
        <Outlet />
      </main>
    </div>
  );
}

