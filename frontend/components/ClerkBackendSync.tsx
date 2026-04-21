"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useRef } from "react";

function apiBase(): string {
  return (
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000"
  );
}

/**
 * POST /auth/clerk/sync after sign-in (including first load with an existing session)
 * and again after each sign-out → sign-in. Idempotent on the backend.
 */
export function ClerkBackendSync() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const prevSignedIn = useRef<boolean | null>(null);

  useEffect(() => {
    if (!isLoaded) return;

    let shouldSync = false;
    if (prevSignedIn.current === null) {
      shouldSync = isSignedIn;
      prevSignedIn.current = isSignedIn;
    } else {
      if (!prevSignedIn.current && isSignedIn) {
        shouldSync = true;
      }
      prevSignedIn.current = isSignedIn;
    }

    if (!shouldSync || !isSignedIn) return;

    void (async () => {
      try {
        const token = await getToken();
        if (!token) return;

        const res = await fetch(`${apiBase()}/auth/clerk/sync`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (!res.ok) {
          const body = await res.text();
          console.error("POST /auth/clerk/sync failed:", res.status, body);
        }
      } catch (e) {
        console.error("POST /auth/clerk/sync error:", e);
      }
    })();
  }, [isLoaded, isSignedIn, getToken]);

  return null;
}
