import { createRootRoute } from "@tanstack/react-router";

import { RootLayout } from "@/components/RootLayout";

/** Root route — provides the app shell via `RootLayout`. */
export const rootRoute = createRootRoute({ component: RootLayout });
