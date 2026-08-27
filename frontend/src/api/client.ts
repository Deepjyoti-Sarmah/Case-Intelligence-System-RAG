import type { QueryRequest, QueryResponse } from "../types";

const BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, "") ?? "";

/**
 * POST /api/v1/query — spec §34.
 * Uses BASE if VITE_API_URL is set (docker frontend -> backend), otherwise
 * relies on Vite proxy (dev host).
 */
export async function postQuery(
  req: QueryRequest,
  opts: { signal?: AbortSignal } = {},
): Promise<QueryResponse> {
  const url = BASE ? `${BASE}/api/v1/query` : "/api/v1/query";
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal: opts.signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    // Surface backend detail for error state; never fabricate answer
    throw new Error(text ? `${res.status}: ${text}` : `Request failed: ${res.status}`);
  }

  const data = (await res.json()) as QueryResponse;

  // Defensive normalisation — Phase 8 will always send these shapes
  return {
    answer: data.answer ?? "",
    sources: Array.isArray(data.sources) ? data.sources : [],
    request_id: data.request_id ?? "",
    metadata: data.metadata,
  };
}
