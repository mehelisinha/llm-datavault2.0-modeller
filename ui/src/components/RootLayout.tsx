import { Link, Outlet } from "@tanstack/react-router";
import { Database, LogOut, UserCircle2 } from "lucide-react";

import { useAuth } from "@/auth/AuthProvider";
import { Button, Icon } from "@/components/ui";
import { ADVANCED_NAV, PRIMARY_NAV, ROUTE_LABELS, WORKFLOW_LABELS } from "@/constants/routes";
import { cn } from "@/lib/cn";

const SHELL_MAX_WIDTH = "max-w-6xl";

/**
 * App shell: top navigation + outlet.
 *
 * When the user is unauthenticated the chrome is suppressed and the route
 * (the login page) renders full-bleed so it can own the entire viewport.
 */
export function RootLayout() {
  const { isAuthenticated, isMsalConfigured, getDisplayName, logout } = useAuth();

  if (!isAuthenticated) {
    return (
      <div className="min-h-full bg-background text-foreground">
        <Outlet />
      </div>
    );
  }

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
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5" title={getDisplayName()}>
              <Icon icon={UserCircle2} size="sm" />
              <span className="max-w-[12rem] truncate">{getDisplayName()}</span>
            </span>
            {isMsalConfigured ? (
              <Button
                intent="ghost"
                size="sm"
                onClick={() => {
                  void logout();
                }}
                leftIcon={<Icon icon={LogOut} size="sm" />}
              >
                Sign out
              </Button>
            ) : null}
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

