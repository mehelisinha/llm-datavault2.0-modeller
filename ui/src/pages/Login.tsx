import { useEffect, useState } from "react";
import { useRouter } from "@tanstack/react-router";
import { Database, LogIn, ShieldCheck } from "lucide-react";

import { useAuth } from "@/auth/AuthProvider";
import { Button, Card, CardContent, Icon, Spinner } from "@/components/ui";
import { LOGIN_LABELS, ROUTES } from "@/constants/routes";
import { env } from "@/env";
import { cn } from "@/lib/cn";

/**
 * Sign-in screen.
 *
 * Pure presentational shell over `useAuth`: branding from env, no hard-coded
 * tenant strings. Renders three states:
 *   1. MSAL configured + signed-out → "Sign in with Microsoft" button.
 *   2. MSAL configured + signed-in  → auto-redirect to the post-login route.
 *   3. MSAL NOT configured          → dev-mode notice + "Continue" button.
 */
export default function LoginPage() {
  const { login, isAuthenticated, isMsalConfigured } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) {
      router.navigate({ to: ROUTES.discovery, replace: true });
    }
  }, [isAuthenticated, router]);

  const handleSignIn = async () => {
    setPending(true);
    setError(null);
    try {
      await login();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      className={cn(
        "relative flex min-h-screen items-center justify-center overflow-hidden px-4",
        "bg-gradient-to-br from-background via-background to-muted",
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            "radial-gradient(60% 50% at 50% 0%, hsl(var(--primary) / 0.18) 0%, transparent 70%)",
        }}
      />
      <Card className="relative z-10 w-full max-w-md border-border/60 shadow-xl backdrop-blur supports-[backdrop-filter]:bg-card/90">
        <CardContent className="space-y-6 p-8">
          <div className="flex flex-col items-center text-center">
            <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 ring-1 ring-primary/20">
              <Icon icon={Database} size="lg" className="text-primary" />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {env.appName}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {env.tenantName} · {LOGIN_LABELS.pageTitle}
            </p>
          </div>

          {isMsalConfigured ? (
            <>
              <Button
                intent="primary"
                size="lg"
                className="w-full"
                disabled={pending}
                onClick={handleSignIn}
                leftIcon={pending ? <Spinner /> : <Icon icon={LogIn} />}
              >
                {pending ? LOGIN_LABELS.signingIn : LOGIN_LABELS.signInButton}
              </Button>
              {error ? (
                <p className="text-sm text-destructive" role="alert">
                  {error}
                </p>
              ) : null}
              <p className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
                <Icon icon={ShieldCheck} size="sm" />
                {LOGIN_LABELS.legal}
              </p>
            </>
          ) : (
            <>
              <div className="rounded-md border border-dashed border-border bg-muted/40 p-3 text-xs text-muted-foreground">
                {LOGIN_LABELS.devModeHint}
              </div>
              <Button
                intent="secondary"
                size="lg"
                className="w-full"
                disabled={pending}
                onClick={handleSignIn}
                leftIcon={pending ? <Spinner /> : null}
              >
                {LOGIN_LABELS.continueDev}
              </Button>
              <p className="text-xs text-muted-foreground">
                {LOGIN_LABELS.disabledHint}
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
