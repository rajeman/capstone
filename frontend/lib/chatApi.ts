import { FINANCIAL_SYSTEM_PROMPT } from "./financialSystemPrompt";
import { publicApiBase } from "./publicApiBase";

export type ChatRole = "user" | "assistant";

export type ChatMessagePayload = {
  role: ChatRole;
  content: string;
};

export type ChatRequestBody = {
  system_prompt: string;
  messages: ChatMessagePayload[];
};

export type ReasoningStepPayload = {
  id: string;
  label: string;
  detail?: string | null;
};

export type ChatResponseBody = {
  message: string;
  reasoning_steps: ReasoningStepPayload[];
};

export async function postChat(
  token: string | null,
  messages: ChatMessagePayload[],
): Promise<ChatResponseBody> {
  const body: ChatRequestBody = {
    system_prompt: FINANCIAL_SYSTEM_PROMPT,
    messages,
  };
  const res = await fetch(`${publicApiBase()}/chat`, {
    method: "POST",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Chat request failed (${res.status})`);
  }
  const data = (await res.json()) as ChatResponseBody;
  return {
    message: data.message,
    reasoning_steps: data.reasoning_steps ?? [],
  };
}
