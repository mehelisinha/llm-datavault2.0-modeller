import { useEffect } from "react";

import { useAuth } from "@/auth/AuthProvider";
import { setDisplayNameResolver } from "@/lib/actor";

/** Wires MSAL / dev display name into the X-Actor header resolver. */
export function ActorBridge() {
  const { getDisplayName } = useAuth();
  useEffect(() => {
    setDisplayNameResolver(getDisplayName);
  }, [getDisplayName]);
  return null;
}
