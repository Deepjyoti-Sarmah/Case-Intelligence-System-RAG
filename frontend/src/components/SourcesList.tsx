import type { Source } from "../types";

type Props = {
  sources: Source[];
};

function formatSource(s: Source): { line1: string; line2: string } {
  const title = s.title || s.source_id || "Untitled source";
  const parts: string[] = [];

  // Prefer section/heading_path for policy/reference docs, session for transcripts
  if (s.heading_path && s.heading_path.length > 0) {
    parts.push(`Section: ${s.heading_path.join(" › ")}`);
  } else if (s.section) {
    parts.push(`Section: ${s.section}`);
  } else if (s.session_id || s.session_date) {
    const session = s.session_id ?? s.session_date ?? "";
    // Try to humanise session_date if ISO
    let label = session;
    if (s.session_date) label = `Session: ${s.session_date}`;
    else if (s.session_id) label = `Session: ${s.session_id}`;
    if (s.person_id) label += ` • ${s.person_id}`;
    parts.push(label);
  } else if (s.document_type) {
    parts.push(`Type: ${s.document_type}`);
  }

  if (s.page != null) parts.push(`Page: ${s.page}`);
  if (s.turn_start != null && s.turn_end != null) parts.push(`Turns: ${s.turn_start}–${s.turn_end}`);

  return { line1: title, line2: parts.join(" • ") };
}

export default function SourcesList({ sources }: Props) {
  if (sources.length === 0) {
    return (
      <section
        aria-label="Sources / Evidence"
        style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, background: "#fff" }}
      >
        <h2 style={{ marginTop: 0, marginBottom: 8, fontSize: 18 }}>Sources / Evidence</h2>
        <p style={{ color: "#666", margin: 0 }}>No sources returned.</p>
      </section>
    );
  }

  return (
    <section
      aria-label="Sources / Evidence"
      style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, background: "#fff" }}
    >
      <h2 style={{ marginTop: 0, marginBottom: 12, fontSize: 18 }}>Sources / Evidence</h2>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
        {sources.map((s, i) => {
          const { line1, line2 } = formatSource(s);
          return (
            <li
              key={s.source_id ?? i}
              style={{
                border: "1px solid #eee",
                borderRadius: 6,
                padding: "10px 12px",
                background: "#fafafa",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 14 }}>{line1}</div>
              {line2 && <div style={{ fontSize: 13, color: "#555", marginTop: 4 }}>{line2}</div>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
