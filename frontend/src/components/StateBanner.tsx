type Props = { status: "idle" | "loading" | "empty" | "error"; error?: string };

export default function StateBanner({ status, error }: Props) {
  if (status === "idle") {
    return (
      <div
        style={{
          color: "#94a3b8",
          margin: "12px 0 20px",
          textAlign: "center",
          fontSize: 14,
          padding: "16px",
          border: "1px dashed #334155",
          borderRadius: 8,
        }}
      >
        Select a sample query above or type a question to perform evidence-grounded search across the corpus.
      </div>
    );
  }
  if (status === "loading") {
    return (
      <div
        role="status"
        aria-live="polite"
        style={{
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: 12,
          padding: 24,
          marginBottom: 20,
          display: "flex",
          alignItems: "center",
          gap: 14,
          boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
        }}
      >
        <span className="spinner" style={{ width: 22, height: 22, borderTopColor: "#6366f1" }} />
        <div>
          <div style={{ fontWeight: 600, color: "#f8fafc", fontSize: 15 }}>Processing Evidence Retrieval & Reasoning</div>
          <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 2 }}>
            Executing query planner, hybrid candidate fusion, and claim grounding...
          </div>
        </div>
      </div>
    );
  }
  if (status === "empty") {
    return (
      <div
        role="status"
        style={{
          background: "rgba(245, 158, 11, 0.1)",
          border: "1px solid rgba(245, 158, 11, 0.3)",
          borderRadius: 12,
          padding: 20,
          marginBottom: 20,
        }}
      >
        <strong style={{ color: "#fbbf24", fontSize: 15, display: "block", marginBottom: 4 }}>No Evidence Found in Corpus</strong>
        <span style={{ color: "#cbd5e1", fontSize: 14 }}>
          The indexed transcripts and reference documents do not contain sufficient evidence to ground an answer to this question.
        </span>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div
        role="alert"
        style={{
          background: "rgba(239, 68, 68, 0.1)",
          border: "1px solid rgba(239, 68, 68, 0.3)",
          padding: 16,
          borderRadius: 12,
          marginBottom: 20,
        }}
      >
        <strong style={{ color: "#f87171", display: "block", marginBottom: 4 }}>Query Execution Error</strong>
        <span style={{ color: "#fca5a5", fontSize: 14, wordBreak: "break-word" }}>{error || "Request failed."}</span>
      </div>
    );
  }
  return null;
}

