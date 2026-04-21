import { verifyToken } from "@clerk/backend";
import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

/** PEM from env often uses literal \n — convert to real newlines. */
function normalizeJwtKey(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  return raw.replace(/\\n/g, "\n");
}

export async function POST() {
  const { getToken } = await auth();
  const token = await getToken();
  if (!token) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const syncSecret = process.env.CLERK_SYNC_SECRET;
  const secretKey = process.env.CLERK_SECRET_KEY;
  const jwtKey = normalizeJwtKey(process.env.CLERK_JWT_KEY);

  if (syncSecret && (secretKey || jwtKey)) {
    try {
      const payload = await verifyToken(token, {
        ...(secretKey ? { secretKey } : {}),
        ...(jwtKey ? { jwtKey } : {}),
      });
      const res = await fetch(`${BACKEND_URL}/auth/clerk/sync`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Clerk-Sync-Secret": syncSecret,
        },
        body: JSON.stringify(payload),
      });
      const text = await res.text();
      return new NextResponse(text, {
        status: res.status,
        headers: {
          "Content-Type": res.headers.get("Content-Type") ?? "application/json",
        },
      });
    } catch (e) {
      console.error("verifyToken failed:", e);
      return NextResponse.json(
        {
          error: "Session token verification failed",
          hint:
            "Use the same Clerk application for NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY, or set CLERK_JWT_KEY (PEM from Clerk Dashboard → API Keys).",
        },
        { status: 401 },
      );
    }
  }

  const res = await fetch(`${BACKEND_URL}/auth/clerk/sync`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/json",
    },
  });
}
