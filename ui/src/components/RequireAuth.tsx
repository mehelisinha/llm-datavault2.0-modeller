import { useEffect } from "react";
import { useRouter } from "@tanstack/react-router";

import { useAuth } from "@/auth/AuthProvider";
import { ROUTES } from "@/constants/routes";

/**
 * Route gate.
 *
 * Redirects unauthenticated callers to `/login`. When MSAL is not configured
 * (dev mode) `isAuthenticated` is always true, so the gate is a no-op and
 * developers retain hot-reload navigation without a sign-in step.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated) {
      router.navigate({ to: ROUTES.login, replace: true });
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) {
    return null;
  }
  return <>{children}</>;
}
