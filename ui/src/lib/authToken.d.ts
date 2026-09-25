export declare function setAccessTokenResolver(resolver: () => Promise<string | null>): void;
export declare function getAccessToken(): Promise<string | null>;
