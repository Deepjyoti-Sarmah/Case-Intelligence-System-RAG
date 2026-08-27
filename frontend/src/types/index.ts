/** Spec §34 API contract + §33 provenance fields. Keep flexible for Phase 8 evolution. */

export type QueryRequest = {
  question: string;
  options?: {
    stream?: boolean;
  };
};

export type Source = {
  source_id?: string;
  title: string;
  document_type?: string; // transcript | policy | service_reference | evidence_based_practice | state_standard
  page?: number | null;
  session_date?: string | null;
  session_id?: string | null;
  section?: string | null;
  heading_path?: string[] | null;
  person_id?: string | null;
  turn_start?: number | null;
  turn_end?: number | null;
};

export type QueryResponse = {
  answer: string;
  sources: Source[];
  request_id: string;
  metadata?: {
    retrieval_count?: number;
    latency_ms?: number;
  };
  // Phase 8 grounding may add these; frontend tolerates them but does not render raw JSON
  claims?: unknown;
  confidence?: string;
};

export type AppStatus = "idle" | "loading" | "success" | "error" | "empty";
