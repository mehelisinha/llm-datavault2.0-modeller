export declare const env: Readonly<{
    apiBaseUrl: string;
    devActor: string;
    msal: Readonly<{
        clientId: string;
        tenantId: string;
        authority: string;
        apiScope: string;
        redirectUri: string;
    }>;
    defaults: Readonly<{
        systemId: string;
        systemName: string;
        recordSource: string;
    }>;
}>;
export type Env = typeof env;
