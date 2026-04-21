"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useRef } from "react";

/**
 * Calls the FastAPI `/auth/clerk/sync` proxy after sign-in so MongoDB gets a user row.
 */
export function ClerkMongoSync() {
  const { isLoaded, userId } = useAuth();
  const lastSynced = useRef<string | null>(null);

  useEffect(() => {
    if (!isLoaded || !userId) {
      lastSynced.current = null;
      return;
    }
    if (lastSynced.current === userId) {
      return;
    }
    lastSynced.current = userId;

    void (async () => {
      try {
        const res = await fetch("/api/clerk-sync", { method: "POST" });
        if (!res.ok) {
          const body = await res.text();
          console.error("Clerk → Mongo sync failed:", res.status, body);
        }
      } catch (e) {
        console.error("Clerk → Mongo sync request failed:", e);
      }
    })();
  }, [isLoaded, userId]);

  return null;
}
