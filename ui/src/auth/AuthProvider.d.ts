import { type ReactNode } from "react";
import { type AccountInfo } from "@azure/msal-browser";
type AuthContextValue = {
    account: AccountInfo | null;
    isAuthenticated: boolean;
    login: () => Promise<void>;
    logout: () => Promise<void>;
    getDisplayName: () => string;
};
export declare function AuthProvider({ children }: {
    children: ReactNode;
}): import("react/jsx-runtime").JSX.Element;
export declare function useAuth(): AuthContextValue;
export {};
