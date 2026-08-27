type Props = { status: "idle" | "loading" | "empty" | "error"; error?: string };

export default function StateBanner({ status, error }: Props) {
  if (status === "idle") {
    return <p style={{ color: "#666", margin: "8px 0 16px" }}>Enter a question to get started.</p>;
  }
  if (status === "loading") {
    return (
      <div
        role="status"
        aria-live="polite"
        style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, background: "#fff", marginBottom: 16 }}
      >
        Loading… retrieving evidence and generating answer.
      </div>
    );
  }
  if (status === "empty") {
    return (
      <div
        role="status"
        style={{ border: "1px solid #e5d3a0", background: "#fffbf0", borderRadius: 8, padding: 16, marginBottom: 16 }}
      >
        <strong>No evidence found.</strong>
        <span style={{ marginLeft: 6, color: "#665" }}>
          The indexed transcripts and reference documents do not contain an answer to this question.
        </span>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div
        role="alert"
        style={{ background: "#fee", border: "1px solid #fcc", padding: 12, borderRadius: 6, marginBottom: 16 }}
      >
        <strong>Error:</strong> <span style={{ marginLeft: 6, wordBreak: "break-word" }}>{error || "Request failed."}</span>
      </div>
    );
  }
  return null;
}
