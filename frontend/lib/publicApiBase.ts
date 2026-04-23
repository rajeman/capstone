/**
 * Base URL for browser calls to the FastAPI app.
 * When unset (typical App Runner: API + static on one origin), use "" so paths are same-origin.
 * Set NEXT_PUBLIC_API_URL at `next build` / Docker build only if the API is on another host.
 */
export function publicApiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";
}
