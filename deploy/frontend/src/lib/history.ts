import type { ChatMessage, Chats } from "../types/chat";

const KEY = "chats:v1";
// Keeps localStorage well under its ~5 MB quota even with long sessions.
const MAX_MESSAGES_PER_DB = 60;

export function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/* Query results are not stored (re-run them instead); an answer cut off by a reload becomes a retryable error. */
function forStorage(m: ChatMessage): ChatMessage {
  if (m.role === "user") return m;
  const { result: _r, execError: _e, ...rest } = m;
  return {
    ...rest,
    editing: false,
    executing: false,
    ...(m.status === "pending" ? { status: "error" as const, error: "This answer was interrupted when the page closed." } : {}),
  };
}

export function loadChats(): Chats {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    const out: Chats = {};
    for (const [db, msgs] of Object.entries(parsed as Record<string, unknown>)) {
      if (Array.isArray(msgs)) {
        out[db] = msgs.filter(
          (m): m is ChatMessage =>
            !!m && typeof m === "object" && typeof m.id === "string" && (m.role === "user" || m.role === "assistant")
        );
      }
    }
    return out;
  } catch {
    return {};
  }
}

export function saveChats(chats: Chats): void {
  try {
    const trimmed: Chats = {};
    for (const [db, msgs] of Object.entries(chats)) {
      if (msgs.length) trimmed[db] = msgs.slice(-MAX_MESSAGES_PER_DB).map(forStorage);
    }
    localStorage.setItem(KEY, JSON.stringify(trimmed));
  } catch {
    // Storage full or blocked: history simply won't survive a reload.
  }
}
