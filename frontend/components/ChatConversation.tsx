"use client";

import { useAuth, useUser } from "@clerk/nextjs";
import { useCallback, useEffect, useRef, useState } from "react";

import { postChat } from "../lib/chatApi";
import type { ChatMessagePayload, ReasoningStepPayload } from "../lib/chatApi";
import type { AnalyticsChartSpec } from "../lib/analyticsChartTypes";

import { ChatMarkdown } from "./ChatMarkdown";
import type { ThinkingState, ThinkingStep } from "./ThinkingStepsPanel";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  at: number;
};

function toThinkingStepsFromReasoning(steps: ReasoningStepPayload[]): ThinkingStep[] {
  return steps.map((s, i) => ({
    id: s.id || `r-${i}`,
    label: s.label,
    detail: s.detail ?? undefined,
    phase: "done" as const,
  }));
}

function toPayload(messages: ChatMessage[]): ChatMessagePayload[] {
  return messages.map((m) => ({ role: m.role, content: m.text }));
}

type ChatConversationProps = {
  onThinkingChange?: (state: ThinkingState) => void;
  onChartsChange?: (charts: AnalyticsChartSpec[]) => void;
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

export function ChatConversation({ onThinkingChange, onChartsChange }: ChatConversationProps) {
  const { user, isLoaded } = useUser();
  const { getToken } = useAuth();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const onThinkingRef = useRef(onThinkingChange);
  const onChartsRef = useRef(onChartsChange);

  useEffect(() => {
    onThinkingRef.current = onThinkingChange;
  }, [onThinkingChange]);

  useEffect(() => {
    onChartsRef.current = onChartsChange;
  }, [onChartsChange]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  const send = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      text: trimmed,
      at: Date.now(),
    };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");

    const token = await getToken();
    if (!token) {
      onThinkingRef.current?.({ active: false, steps: [] });
      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          text: "Could not read your session. Please sign in again.",
          at: Date.now(),
        },
      ]);
      return;
    }

    onThinkingRef.current?.({
      active: true,
      steps: [
        {
          id: "progress",
          label: "Working on your message…",
          phase: "running",
        },
      ],
    });
    onChartsRef.current?.([]);
    setSending(true);

    try {
      const { message, reasoning_steps, charts } = await postChat(token, toPayload(nextMessages));
      const assistantMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        text: message,
        at: Date.now(),
      };
      setMessages((m) => [...m, assistantMsg]);
      const panelSteps = toThinkingStepsFromReasoning(reasoning_steps);
      onThinkingRef.current?.({
        active: false,
        steps:
          panelSteps.length > 0
            ? panelSteps
            : [
                {
                  id: "summary-missing",
                  label: "All set",
                  detail: "No quick recap this time — your answer is in the chat.",
                  phase: "done",
                },
              ],
      });
      onChartsRef.current?.(charts);
    } catch (e) {
      const detail = e instanceof Error ? e.message : "Something went wrong.";
      const assistantMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        text: `Sorry, I couldn’t reach the assistant: ${detail}`,
        at: Date.now(),
      };
      setMessages((m) => [...m, assistantMsg]);
      onThinkingRef.current?.({
        active: false,
        steps: [
          {
            id: "error",
            label: "Could not complete the request",
            detail,
            phase: "done",
          },
        ],
      });
      onChartsRef.current?.([]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }, [input, sending, messages, getToken]);

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
      aria-label="Chat with Smart Pay"
    >
      <header className="shrink-0 border-b border-blue-100/80 px-5 py-4 dark:border-gray-700/80">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold tracking-tight text-gray-900 dark:text-gray-50">
            Smart Pay
          </h2>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200/80 dark:bg-emerald-950/50 dark:text-emerald-400 dark:ring-emerald-800/80">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            online
          </span>
        </div>
        <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
          Financial transactions and questions by chat
        </p>
      </header>

      <div
        ref={scrollRef}
        className="chat-scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-5"
      >
        {messages.length === 0 && !sending && (
          <p className="rounded-2xl border border-dashed border-blue-200/80 bg-white/50 px-4 py-6 text-center text-sm text-gray-600 dark:border-gray-600 dark:bg-gray-900/30 dark:text-gray-400">
            Hi{user.firstName ? `, ${user.firstName}` : ""}. Smart Pay is your conversational wallet:
            send money, check balances, review recent activity, look up people by name, and ask
            anything about your account—in plain language.
          </p>
        )}
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
              <ChatMarkdown content={m.text} variant={m.role} />
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
