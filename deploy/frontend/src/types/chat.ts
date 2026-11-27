import type { ExecuteResponse, GenerateResponse } from "./api";

export interface UserMessage {
  id: string;
  role: "user";
  text: string;
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  question: string;
  status: "pending" | "done" | "error";
  error?: string;
  generation?: GenerateResponse;
  sql: string;
  editing: boolean;
  executing: boolean;
  result?: ExecuteResponse;
  execError?: string;
}

export type ChatMessage = UserMessage | AssistantMessage;
