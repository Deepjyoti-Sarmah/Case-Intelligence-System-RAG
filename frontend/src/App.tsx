import { useState } from "react";

type Status = "idle" | "loading" | "success" | "error" | "empty";

export default function App() {
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Array<{ title: string; page?: number }>>([]);
  const [error, setError] = useState("");

  const ask = async () => {
    if (!question.trim()) return;
    setStatus("loading");
    setError("");
    try {
      const res = await fetch("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`${res.status}: ${text}`);
      }
      const data = await res.json();
      if (!data.answer) {
        setStatus("empty");
      } else {
        setAnswer(data.answer);
        setSources(data.sources ?? []);
        setStatus("success");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus("error");
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <h1>AI Case Intelligence</h1>

      <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, marginBottom: 16 }}>
        <label htmlFor="q" style={{ display: "block", marginBottom: 8, fontWeight: 600 }}>
          Ask a question
        </label>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            id="q"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="e.g. When should a client submit a grievance?"
            style={{ flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid #ccc" }}
          />
          <button
            onClick={ask}
            disabled={status === "loading"}
            style={{ padding: "8px 16px", borderRadius: 6, border: "none", background: "#111", color: "#fff", cursor: "pointer" }}
          >
            {status === "loading" ? "Asking…" : "Ask"}
          </button>
        </div>
      </div>

      {status === "idle" && <p style={{ color: "#666" }}>Enter a question to get started.</p>}
      {status === "loading" && <p>Loading…</p>}
      {status === "error" && (
        <div style={{ background: "#fee", border: "1px solid #fcc", padding: 12, borderRadius: 6 }}>
          <strong>Error:</strong> {error}
        </div>
      )}
      {status === "empty" && <p>No evidence found for this question.</p>}
      {status === "success" && (
        <>
          <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <h2 style={{ marginTop: 0 }}>Answer</h2>
            <p style={{ whiteSpace: "pre-wrap" }}>{answer}</p>
          </div>
          <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
            <h2 style={{ marginTop: 0 }}>Sources / Evidence</h2>
            {sources.length === 0 ? (
              <p style={{ color: "#666" }}>No sources returned.</p>
            ) : (
              <ul>
                {sources.map((s, i) => (
                  <li key={i}>
                    {s.title} {s.page ? `— Page ${s.page}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
