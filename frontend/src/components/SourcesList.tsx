import type { Source } from "../types";

type Props = {
  sources: Source[];
};

function formatSource(s: Source): { title: string; subtitle: string; docType: string } {
  const title = s.title || s.source_id || "Untitled source";
  const parts: string[] = [];

  if (s.heading_path && s.heading_path.length > 0) {
    parts.push(`Section: ${s.heading_path.join(" › ")}`);
  } else if (s.section) {
    parts.push(`Section: ${s.section}`);
  } else if (s.session_id || s.session_date) {
    let label = s.session_date ? `Session: ${s.session_date}` : `Session: ${s.session_id}`;
    if (s.person_id) label += ` • Client: ${s.person_id.toUpperCase()}`;
    parts.push(label);
  }

  if (s.page != null) parts.push(`Page ${s.page}`);
  if (s.turn_start != null && s.turn_end != null) parts.push(`Turns ${s.turn_start}–${s.turn_end}`);

  const docType = (s.document_type || "document").replace(/_/g, " ").toUpperCase();

  return { title, subtitle: parts.join(" • "), docType };
}

export default function SourcesList({ sources }: Props) {
  if (sources.length === 0) {
    return (
      <section
        aria-label="Sources / Evidence"
        style={{
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: 12,
          padding: 20,
          boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
        }}
      >
        <h2 style={{ marginTop: 0, marginBottom: 8, fontSize: 18, fontWeight: 600, color: "#f8fafc" }}>
          Retrieved Evidence & Provenance
        </h2>
        <p style={{ color: "#94a3b8", margin: 0, fontSize: 14 }}>No evidence sources attached.</p>
      </section>
    );
  }

  return (
    <section
      aria-label="Sources / Evidence"
      style={{
        background: "#1e293b",
        border: "1px solid #334155",
        borderRadius: 12,
        padding: 20,
        boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: "#f8fafc" }}>
          Retrieved Evidence & Provenance
        </h2>
        <span style={{ fontSize: 12, color: "#94a3b8" }}>{sources.length} sources cited</span>
      </div>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 12 }}>
        {sources.map((s, i) => {
          const { title, subtitle, docType } = formatSource(s);
          const isTranscript = s.document_type === "transcript" || docType.includes("TRANSCRIPT");
          const pillBg = isTranscript ? "rgba(99, 102, 241, 0.15)" : "rgba(14, 165, 233, 0.15)";
          const pillText = isTranscript ? "#818cf8" : "#38bdf8";
          const pillBorder = isTranscript ? "rgba(99, 102, 241, 0.3)" : "rgba(14, 165, 233, 0.3)";

          return (
            <li
              key={s.source_id ?? i}
              style={{
                border: "1px solid #334155",
                borderRadius: 8,
                padding: "12px 16px",
                background: "#0f172a",
                transition: "border-color 0.2s",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14, color: "#f1f5f9" }}>{title}</div>
                  {subtitle && <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 4 }}>{subtitle}</div>}
                </div>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: 12,
                    background: pillBg,
                    color: pillText,
                    border: `1px solid ${pillBorder}`,
                    whiteSpace: "nowrap",
                  }}
                >
                  {docType}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

