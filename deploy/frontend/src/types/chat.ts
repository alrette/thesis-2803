import type { ExecuteResponse, GenerateResponse } from "./api";

export interface UserMessage {
  id: string;
  role: "user";
  text: string;
  createdAt: number;
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  question: string;
  createdAt: number;
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

export type Chats = Record<string, ChatMessage[]>;
