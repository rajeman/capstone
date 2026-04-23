"use client";

export type ThinkingStep = {
  id: string;
  label: string;
  /** Optional short subtitle (keep non-technical). */
  detail?: string;
  phase: "pending" | "running" | "done";
};

export type ThinkingState = {
  active: boolean;
  steps: ThinkingStep[];
};

type ThinkingStepsPanelProps = {
  state: ThinkingState;
};

export function ThinkingStepsPanel({ state }: ThinkingStepsPanelProps) {
  const { active, steps } = state;
  const showPlaceholder = !active && steps.length === 0;

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col" aria-live="polite">
      <header className="shrink-0 border-b border-blue-100/80 px-5 py-4 dark:border-gray-700/80">
        <p className="text-base font-semibold tracking-tight text-gray-900 dark:text-gray-50">
          What we did
        </p>
        <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
          {active
            ? "Hang tight…"
            : steps.length > 0
              ? "Quick recap — nothing sensitive here"
              : "A short recap will show here after you send a message"}
        </p>
      </header>

      <div className="chat-scroll min-h-0 flex-1 overflow-y-auto px-5 py-5">
        {showPlaceholder && (
          <p className="text-sm leading-relaxed text-gray-600 dark:text-gray-400">
            After you send a message, a few plain-language steps may appear here while the assistant
            works.
          </p>
        )}

        {!showPlaceholder && (
          <ol className="space-y-3">
            {steps.map((step, index) => (
              <li key={step.id} className="flex gap-3 text-sm">
                <span
                  className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium"
                  aria-hidden
                >
                  {step.phase === "done" ? (
                    <span className="text-emerald-600 dark:text-emerald-400">✓</span>
                  ) : step.phase === "running" ? (
                    <span className="relative flex h-2 w-2">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-600" />
                    </span>
                  ) : (
                    <span className="text-gray-300 dark:text-gray-600">{index + 1}</span>
                  )}
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className={
                      step.phase === "done"
                        ? "text-gray-700 dark:text-gray-300"
                        : step.phase === "running"
                          ? "font-medium text-gray-900 dark:text-gray-100"
                          : "text-gray-400 dark:text-gray-500"
                    }
                  >
                    {step.label}
                  </span>
                  {step.detail ? (
                    <span className="mt-1 block text-xs font-normal leading-snug text-gray-500 dark:text-gray-500">
                      {step.detail}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
