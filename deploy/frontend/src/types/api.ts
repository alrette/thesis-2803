export interface HealthResponse {
  status: string;
  ready: boolean;
  llm_configured: boolean;
  database_count: number;
  pipeline: string;
  embedding_model: string;
  llm_model: string;
  llm_api_mode?: string;
  table_threshold: number;
  few_shot_k: number;
  error: string | null;
}

export interface DatabaseSummary {
  db_id: string;
  display_name: string;
  description: string;
  table_count: number;
  column_count: number;
  fk_count: number;
  sample_question_count: number;
}

export interface ColumnInfo {
  name: string;
  natural_name: string;
  type: string;
  is_pk: boolean;
  is_fk: boolean;
  references: string | null;
}

export interface TableInfo {
  id: string;
  node_id: string;
  name: string;
  natural_name: string;
  columns: ColumnInfo[];
}

export interface ForeignKeyEdge {
  id: string;
  source: string;
  source_column: string;
  target: string;
  target_column: string;
}

export interface SampleQuestion {
  question: string;
  difficulty: "Easy" | "Medium" | "Hard" | string;
}

export interface DatabaseDetail {
  db_id: string;
  display_name: string;
  description: string;
  table_count: number;
  column_count: number;
  fk_count: number;
  tables: TableInfo[];
  edges: ForeignKeyEdge[];
  sample_questions: SampleQuestion[];
}

export interface FewShotItem {
  question: string;
  sql: string;
  db_id: string;
  score: number;
}

export interface GenerateResponse {
  db_id: string;
  question: string;
  sql: string;
  selected_tables: string[];
  detected_tables: string[];
  bridge_tables: string[];
  table_scores: Record<string, number>;
  schema_ddl: string;
  question_skeleton: string | null;
  few_shot_k: number;
  few_shot_examples: FewShotItem[];
  model: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  retrieval_ms: number;
  generation_ms: number;
  total_ms: number;
}

export interface ExecuteResponse {
  ok: boolean;
  columns: string[];
  rows: (string | number | boolean | null)[][];
  row_count: number;
  truncated: boolean;
  execution_ms: number;
  error: string | null;
}
