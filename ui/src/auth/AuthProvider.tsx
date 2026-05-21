import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  EventType,
  PublicClientApplication,
  type AccountInfo,
  type AuthenticationResult,
  InteractionRequiredAuthError,
} from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";

import { env } from "@/env";
import { setAccessTokenResolver } from "@/lib/authToken";

type AuthContextValue = {
  account: AccountInfo | null;
  isAuthenticated: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  getDisplayName: () => string;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function buildMsalInstance(): PublicClientApplication | null {
  if (!env.msal.clientId) {
    return null;
  }
  return new PublicClientApplication({
    auth: {
      clientId: env.msal.clientId,
      authority: env.msal.authority,
      redirectUri: env.msal.redirectUri,
    },
    cache: { cacheLocation: "sessionStorage" },
  });
}

const msalInstance = buildMsalInstance();

function AuthContextProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<AccountInfo | null>(
    () => msalInstance?.getAllAccounts()[0] ?? null,
  );

  useEffect(() => {
    if (!msalInstance) {
      return;
    }
    const callbackId = msalInstance.addEventCallback((event) => {
      if (
        event.eventType === EventType.LOGIN_SUCCESS &&
        event.payload &&
        "account" in event.payload
      ) {
        const payload = event.payload as AuthenticationResult;
        setAccount(payload.account);
      }
      if (event.eventType === EventType.LOGOUT_SUCCESS) {
        setAccount(null);
      }
    });
    return () => {
      if (callbackId) {
        msalInstance.removeEventCallback(callbackId);
      }
    };
  }, []);

  useEffect(() => {
    setAccessTokenResolver(async () => {
      if (!msalInstance || !account) {
        return null;
      }
      const scopes = env.msal.apiScope ? [env.msal.apiScope] : [];
      try {
        const result = await msalInstance.acquireTokenSilent({
          account,
          scopes,
        });
        return result.accessToken;
      } catch (err) {
        if (err instanceof InteractionRequiredAuthError) {
          const result = await msalInstance.acquireTokenPopup({ scopes, account });
          return result.accessToken;
        }
        throw err;
      }
    });
  }, [account]);

  const login = useCallback(async () => {
    if (!msalInstance) {
      return;
    }
    const scopes = env.msal.apiScope ? [env.msal.apiScope] : ["openid", "profile"];
    const result = await msalInstance.loginPopup({ scopes });
    setAccount(result.account);
  }, []);

  const logout = useCallback(async () => {
    if (!msalInstance) {
      return;
    }
    const active = msalInstance.getActiveAccount() ?? account;
    if (active) {
      await msalInstance.logoutPopup({ account: active });
    }
    setAccount(null);
  }, [account]);

  const getDisplayName = useCallback(() => {
    if (account?.username) {
      return account.username;
    }
    return env.devActor;
  }, [account]);

  const value = useMemo(
    () => ({
      account,
      isAuthenticated: Boolean(account),
      login,
      logout,
      getDisplayName,
    }),
    [account, login, logout, getDisplayName],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  if (!msalInstance) {
    return <AuthContextProvider>{children}</AuthContextProvider>;
  }
  return (
    <MsalProvider instance={msalInstance}>
      <AuthContextProvider>{children}</AuthContextProvider>
    </MsalProvider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
