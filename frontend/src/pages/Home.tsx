import { useRef, useState } from "react";
import { postQuery } from "../api/client";
import AnswerPanel from "../components/AnswerPanel";
import QuestionInput from "../components/QuestionInput";
import SourcesList from "../components/SourcesList";
import StateBanner from "../components/StateBanner";
import type { AppStatus, Source } from "../types";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState<AppStatus>("idle");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [groundingStatus, setGroundingStatus] = useState<"SUPPORTED" | "PARTIALLY_SUPPORTED" | "NO_EVIDENCE">("SUPPORTED");
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const ask = async (questionOverride?: string) => {
    const q = (questionOverride ?? question).trim();
    if (!q) return;

    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setStatus("loading");
    setError("");
    try {
      const data = await postQuery({ question: q, options: { stream: false } }, { signal: ac.signal });

      const statusFromMeta = data.metadata?.grounding_status;
      const isNoEvidence = statusFromMeta === "NO_EVIDENCE" || !data.answer || data.answer.trim().length === 0;

      if (isNoEvidence) {
        setAnswer("");
        setSources(data.sources ?? []);
        setGroundingStatus("NO_EVIDENCE");
        setStatus("empty");
        return;
      }

      setAnswer(data.answer);
      setSources(data.sources ?? []);
      setGroundingStatus((statusFromMeta as any) || "SUPPORTED");
      setStatus("success");
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(e instanceof Error ? e.message : String(e));
      setStatus("error");
    }
  };

  return (
    <div
      style={{
        maxWidth: 900,
        margin: "0 auto",
        padding: "32px 20px 48px",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        minHeight: "100vh",
      }}
    >
      <header
        style={{
          marginBottom: 28,
          paddingBottom: 20,
          borderBottom: "1px solid #334155",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: "linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 700,
              color: "#ffffff",
              fontSize: 18,
            }}
          >
            CI
          </div>
          <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, letterSpacing: "-0.5px", color: "#f8fafc" }}>
            Case Intelligence System
          </h1>
        </div>
        <p style={{ margin: 0, color: "#94a3b8", fontSize: 14, lineHeight: 1.5 }}>
          Evidence retrieval & cross-source reasoning application over client transcripts and correctional policies.
        </p>
      </header>

      <QuestionInput value={question} onChange={setQuestion} onAsk={ask} disabled={status === "loading"} />

      {status !== "success" ? (
        <StateBanner status={status as "idle" | "loading" | "empty" | "error"} error={error} />
      ) : null}

      {status === "success" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <AnswerPanel answer={answer} groundingStatus={groundingStatus} />
          <SourcesList sources={sources} />
        </div>
      )}

      {status === "empty" && sources.length > 0 && <SourcesList sources={sources} />}

      <footer
        style={{
          marginTop: 40,
          paddingTop: 16,
          borderTop: "1px solid #1e293b",
          color: "#64748b",
          fontSize: 12,
          textAlign: "center",
        }}
      >
        Evidence is retrieved before LLM generation • Citations come from database provenance • Speaker attribution defaults to unknown
      </footer>
    </div>
  );
}

