"use client";

import { useUser } from "@clerk/nextjs";
import { useCallback, useEffect, useRef, useState } from "react";

import type { ThinkingState } from "./ThinkingStepsPanel";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  at: number;
};

const ASSISTANT_REPLIES = [
  "I’m here to help you shape ideas. Tell me more about the problem you want to solve or the audience you care about.",
  "That’s a solid direction. What constraints do you have — time, budget, or tech stack?",
  "Consider starting with a narrow wedge: one persona, one workflow, one clear outcome.",
  "When you’re ready, you can open the full generator from the header for a deeper pass.",
];

function randomReply(): string {
  return ASSISTANT_REPLIES[Math.floor(Math.random() * ASSISTANT_REPLIES.length)];
}

const THINKING_LABELS = [
  "Parse your message",
  "Recall conversation context",
  "Draft a response",
];

function buildThinkingSteps(
  index: number,
): { id: string; label: string; phase: "pending" | "running" | "done" }[] {
  return THINKING_LABELS.map((label, j) => ({
    id: `t-${j}`,
    label,
    phase: (j < index ? "done" : j === index ? "running" : "pending") as
      | "pending"
      | "running"
      | "done",
  }));
}

type ChatConversationProps = {
  onThinkingChange?: (state: ThinkingState) => void;
};

function PaperPlaneIcon(props: { className?: string }) {
  return (
    <svg
      className={props.className}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2}
      stroke="currentColor"
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 12 3.269 3.126A59.768 59.768 0 0 1 21.485 12 59.77 59.77 0 0 1 3.27 20.876L5.999 12Zm0 0h7.5"
      />
    </svg>
  );
}

function PaperclipIcon(props: { className?: string }) {
  return (
    <svg className={props.className} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.75}
        d="m18.375 12.739-7.693 7.693a4.5 4.5 0 0 1-6.364-6.364l10.94-10.94A3 3 0 1 1 19.5 7.372L8.552 18.32m.009-.01-.01.01m5.699-9.193-2.138 2.14H14.5"
      />
    </svg>
  );
}

export function ChatConversation({ onThinkingChange }: ChatConversationProps) {
  const { user, isLoaded } = useUser();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const onThinkingRef = useRef(onThinkingChange);
  onThinkingRef.current = onThinkingChange;

  const firstName = user?.firstName || user?.username || "there";

  useEffect(() => {
    if (!isLoaded || !user || messages.length > 0) return;
    setMessages([
      {
        id: `a-${Date.now()}`,
        role: "assistant",
        text: `Hi ${firstName}! I'm your IdeaGen assistant. What would you like to explore today?`,
        at: Date.now(),
      },
    ]);
  }, [isLoaded, user, firstName, messages.length]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  useEffect(() => {
    if (!sending) {
      onThinkingRef.current?.({ active: false, steps: [] });
      return;
    }

    onThinkingRef.current?.({ active: true, steps: buildThinkingSteps(0) });

    const timers: ReturnType<typeof setTimeout>[] = [];
    for (let i = 1; i < THINKING_LABELS.length; i++) {
      timers.push(
        setTimeout(() => {
          onThinkingRef.current?.({ active: true, steps: buildThinkingSteps(i) });
        }, 180 + i * 260),
      );
    }

    return () => {
      timers.forEach(clearTimeout);
    };
  }, [sending]);

  const send = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      text: trimmed,
      at: Date.now(),
    };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setSending(true);

    await new Promise((r) => setTimeout(r, 600 + Math.random() * 400));

    const assistantMsg: ChatMessage = {
      id: `a-${Date.now()}`,
      role: "assistant",
      text: randomReply(),
      at: Date.now(),
    };
    setMessages((m) => [...m, assistantMsg]);
    setSending(false);
    inputRef.current?.focus();
  }, [input, sending]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  if (!isLoaded || !user) {
    return (
      <div className="flex flex-1 items-center justify-center p-8 text-sm text-gray-500 dark:text-gray-400">
        Loading chat…
      </div>
    );
  }

  return (
    <div
      className="flex min-h-0 flex-1 flex-col"
      role="region"
      aria-label="Chat with IdeaGen assistant"
    >
      <header className="shrink-0 border-b border-blue-100/80 px-5 py-4 dark:border-gray-700/80">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold tracking-tight text-gray-900 dark:text-gray-50">
            IdeaGen assistant
          </h2>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200/80 dark:bg-emerald-950/50 dark:text-emerald-400 dark:ring-emerald-800/80">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            online
          </span>
        </div>
        <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">Conversation</p>
      </header>

      <div
        ref={scrollRef}
        className="chat-scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-5"
      >
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[90%] text-sm leading-relaxed shadow-sm ${
                m.role === "user"
                  ? "rounded-3xl rounded-br-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-3 text-white shadow-blue-900/10"
                  : "rounded-3xl rounded-bl-lg border border-white/80 bg-white px-4 py-3 text-gray-800 shadow-md ring-1 ring-blue-100/50 dark:border-gray-600 dark:bg-gray-800/90 dark:text-gray-100 dark:ring-gray-700/50"
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="flex gap-1 rounded-3xl rounded-bl-lg border border-white/80 bg-white px-4 py-3 shadow-md ring-1 ring-blue-100/50 dark:border-gray-600 dark:bg-gray-800/90 dark:ring-gray-700/50">
              <span className="h-2 w-2 animate-bounce rounded-full bg-blue-400 [animation-delay:-0.3s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-indigo-400 [animation-delay:-0.15s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-violet-400" />
            </div>
          </div>
        )}
      </div>

      <footer className="shrink-0 border-t border-blue-100/80 p-4 dark:border-gray-700/80">
        <div className="flex items-end gap-2 rounded-2xl border border-white/70 bg-white/90 p-2 shadow-inner ring-1 ring-blue-100/40 backdrop-blur-sm dark:border-gray-600/80 dark:bg-gray-900/60 dark:ring-gray-700/40">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Message..."
            rows={1}
            className="max-h-32 min-h-[48px] flex-1 resize-none bg-transparent px-3 py-3 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none dark:text-gray-100 dark:placeholder:text-gray-500"
          />
          <button
            type="button"
            className="mb-1.5 shrink-0 rounded-xl p-2.5 text-gray-400 transition hover:bg-blue-50 hover:text-blue-600 dark:hover:bg-gray-800 dark:hover:text-blue-400"
            aria-label="Attach file"
          >
            <PaperclipIcon className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={() => void send()}
            disabled={!input.trim() || sending}
            className="mb-1.5 flex shrink-0 items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-900/15 transition hover:from-blue-500 hover:to-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <PaperPlaneIcon className="h-4 w-4" />
            Send
          </button>
        </div>
        <p className="mt-3 text-center text-[11px] text-gray-400 dark:text-gray-500">
          Enter to send · Shift+Enter for newline
        </p>
      </footer>
    </div>
  );
}
