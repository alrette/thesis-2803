import type { ChatMessage, Conversation, Conversations } from "../types/chat";

const KEY = "conversations:v2";
const LEGACY_KEY = "chats:v1";
// Keeps localStorage well under its ~5 MB quota even with long sessions.
const MAX_CONVERSATIONS = 80;
const MAX_MESSAGES_PER_CONVERSATION = 60;

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

const isMessage = (m: unknown): m is ChatMessage =>
  !!m &&
  typeof m === "object" &&
  typeof (m as ChatMessage).id === "string" &&
  ((m as ChatMessage).role === "user" || (m as ChatMessage).role === "assistant");

function readJson(key: string): unknown {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/* The first version stored one conversation per database; each becomes its own conversation. */
function fromLegacy(parsed: unknown): Conversations {
  const out: Conversations = {};
  if (!parsed || typeof parsed !== "object") return out;
  for (const [dbId, msgs] of Object.entries(parsed as Record<string, unknown>)) {
    const messages = Array.isArray(msgs) ? msgs.filter(isMessage) : [];
    if (!messages.length) continue;
    const id = newId();
    out[id] = {
      id,
      dbId,
      createdAt: messages[0].createdAt ?? Date.now(),
      updatedAt: messages[messages.length - 1].createdAt ?? Date.now(),
      messages,
    };
  }
  return out;
}

export function loadConversations(): Conversations {
  const parsed = readJson(KEY);
  if (!parsed || typeof parsed !== "object") return fromLegacy(readJson(LEGACY_KEY));
  const out: Conversations = {};
  for (const c of Object.values(parsed as Record<string, unknown>)) {
    const conv = c as Conversation;
    if (conv && typeof conv.id === "string" && typeof conv.dbId === "string" && Array.isArray(conv.messages)) {
      out[conv.id] = { ...conv, messages: conv.messages.filter(isMessage) };
    }
  }
  return out;
}

export function saveConversations(conversations: Conversations): void {
  try {
    const kept = Object.values(conversations)
      .filter((c) => c.messages.length > 0)
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, MAX_CONVERSATIONS);
    const out: Record<string, Conversation> = {};
    for (const c of kept) {
      out[c.id] = { ...c, messages: c.messages.slice(-MAX_MESSAGES_PER_CONVERSATION).map(forStorage) };
    }
    localStorage.setItem(KEY, JSON.stringify(out));
    localStorage.removeItem(LEGACY_KEY);
  } catch {
    // Storage full or blocked: history simply won't survive a reload.
  }
}

/* Most recent conversation for a database, or null when it has none. */
export function latestConversation(conversations: Conversations, dbId: string): Conversation | null {
  let best: Conversation | null = null;
  for (const c of Object.values(conversations)) {
    if (c.dbId === dbId && c.messages.length > 0 && (!best || c.updatedAt > best.updatedAt)) best = c;
  }
  return best;
}
