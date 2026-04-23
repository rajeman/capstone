import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

type ChatMarkdownProps = {
  content: string;
  variant: "user" | "assistant";
};

function buildComponents(variant: "user" | "assistant"): Components {
  const user = variant === "user";
  const linkClass = user
    ? "text-blue-100 underline decoration-blue-200/80 underline-offset-2 hover:text-white"
    : "text-blue-600 underline underline-offset-2 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300";
  const inlineCode = user
    ? "rounded bg-white/20 px-1 py-0.5 font-mono text-[0.9em]"
    : "rounded bg-gray-100 px-1 py-0.5 font-mono text-[0.9em] dark:bg-gray-700";
  const preClass = user
    ? "my-2 overflow-x-auto rounded-lg bg-black/25 p-3 font-mono text-[0.85em] leading-relaxed"
    : "my-2 overflow-x-auto rounded-lg bg-gray-100 p-3 font-mono text-[0.85em] leading-relaxed dark:bg-gray-900/80";
  const borderMuted = user ? "border-white/35" : "border-gray-200 dark:border-gray-600";

  return {
    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
    ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
    ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
    li: ({ children }) => <li>{children}</li>,
    a: ({ href, children }) => (
      <a href={href} target="_blank" rel="noopener noreferrer" className={linkClass}>
        {children}
      </a>
    ),
    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
    em: ({ children }) => <em className="italic">{children}</em>,
    code: ({ className, children, ...props }) => {
      const isBlock = Boolean(className?.startsWith("language-"));
      if (isBlock) {
        return (
          <code className={`${user ? "text-white/95" : "text-gray-900 dark:text-gray-100"} ${className ?? ""}`} {...props}>
            {children}
          </code>
        );
      }
      return (
        <code className={inlineCode} {...props}>
          {children}
        </code>
      );
    },
    pre: ({ children }) => <pre className={preClass}>{children}</pre>,
    h1: ({ children }) => <h1 className="mb-2 text-base font-semibold">{children}</h1>,
    h2: ({ children }) => <h2 className="mb-2 text-sm font-semibold">{children}</h2>,
    h3: ({ children }) => <h3 className="mb-1 text-sm font-semibold">{children}</h3>,
    blockquote: ({ children }) => (
      <blockquote
        className={`my-2 border-l-2 pl-3 italic ${user ? "border-white/50" : "border-gray-300 dark:border-gray-500"}`}
      >
        {children}
      </blockquote>
    ),
    hr: () => <hr className={`my-3 ${user ? "border-white/30" : "border-gray-200 dark:border-gray-600"}`} />,
    table: ({ children }) => (
      <div className="my-2 overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-[0.9em]">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead>{children}</thead>,
    tbody: ({ children }) => <tbody>{children}</tbody>,
    tr: ({ children }) => <tr>{children}</tr>,
    th: ({ children }) => (
      <th className={`border px-2 py-1 font-semibold ${borderMuted}`}>{children}</th>
    ),
    td: ({ children }) => <td className={`border px-2 py-1 ${borderMuted}`}>{children}</td>,
  };
}

export function ChatMarkdown({ content, variant }: ChatMarkdownProps) {
  return (
    <div className="min-w-0 break-words [&_p]:leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={buildComponents(variant)}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
