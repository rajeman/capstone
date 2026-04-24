"use client";

import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback, useState } from "react";
import { RedirectToSignIn, SignedIn, SignedOut, UserButton } from "@clerk/nextjs";
import { ChatConversation } from "../components/ChatConversation";
import {
  ThinkingStepsPanel,
  type ThinkingState,
} from "../components/ThinkingStepsPanel";

export default function ChatPage() {
  const router = useRouter();
  const [thinking, setThinking] = useState<ThinkingState>({
    active: false,
    steps: [],
  });

  const handleThinkingChange = useCallback((state: ThinkingState) => {
    setThinking(state);
  }, []);

  const startNewChat = useCallback(() => {
    if (router.pathname === "/chat") {
      router.reload();
      return;
    }
    void router.push("/chat");
  }, [router]);

  return (
    <>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
      <SignedIn>
        <main className="relative flex min-h-screen flex-col overflow-hidden bg-gradient-to-br from-blue-50 via-indigo-50/80 to-violet-100/90 dark:from-gray-950 dark:via-gray-900 dark:to-indigo-950/40">
          <div className="pointer-events-none absolute bottom-6 right-8 text-white/30 dark:text-white/10">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              <path d="M12 0l2.4 9.6L24 12l-9.6 2.4L12 24l-2.4-9.6L0 12l9.6-2.4L12 0z" />
            </svg>
          </div>

          <div className="container mx-auto flex min-h-0 flex-1 flex-col px-4 py-8">
            <nav className="mb-6 flex shrink-0 items-center justify-between">
              <Link
                href="/"
                className="text-2xl font-bold text-gray-800 dark:text-gray-100"
              >
                Smart Pay
              </Link>
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={startNewChat}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700"
                >
                  New Chat
                </button>
                <UserButton afterSignOutUrl="/" />
              </div>
            </nav>

            <h1 className="mb-5 shrink-0 text-xl font-semibold text-gray-800 dark:text-gray-200">
              Transact in conversation
            </h1>

            <div
              className="grid min-h-[min(520px,calc(100vh-11rem))] flex-1 grid-cols-1 overflow-hidden rounded-3xl border border-white/60 bg-white/45 shadow-[0_8px_40px_-4px_rgba(59,130,246,0.18)] backdrop-blur-xl dark:border-white/10 dark:bg-gray-950/35 dark:shadow-black/30 lg:grid-cols-[3fr_2fr]"
            >
              <div className="flex min-h-0 min-w-0 flex-col">
                <ChatConversation onThinkingChange={handleThinkingChange} />
              </div>

              <aside className="flex min-h-[220px] min-w-0 flex-col border-t border-blue-400 dark:border-gray-400 lg:min-h-0 lg:border-l lg:border-t-0">
                <ThinkingStepsPanel state={thinking} />
              </aside>
            </div>
          </div>
        </main>
      </SignedIn>
    </>
  );
}
