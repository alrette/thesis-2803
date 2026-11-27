import type {
  DatabaseDetail,
  DatabaseSummary,
  ExecuteResponse,
  GenerateResponse,
  HealthResponse,
} from "../types/api";

const RAW_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:7860";
export const API_BASE_URL = RAW_BASE.replace(/\/+$/, "");

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new Error(detail);
  }

  return (await res.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health");
}

export async function fetchDatabases(): Promise<DatabaseSummary[]> {
  const data = await requestJson<{ databases: DatabaseSummary[] }>("/api/databases");
  return data.databases;
}

export function fetchDatabaseDetail(dbId: string): Promise<DatabaseDetail> {
  return requestJson<DatabaseDetail>(`/api/databases/${encodeURIComponent(dbId)}`);
}

export function generateSql(dbId: string, question: string): Promise<GenerateResponse> {
  return requestJson<GenerateResponse>("/api/generate", {
    method: "POST",
    body: JSON.stringify({ db_id: dbId, question }),
  });
}

export function executeSql(dbId: string, sql: string): Promise<ExecuteResponse> {
  return requestJson<ExecuteResponse>("/api/execute", {
    method: "POST",
    body: JSON.stringify({ db_id: dbId, sql }),
  });
}
