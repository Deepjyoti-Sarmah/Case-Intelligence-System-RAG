type Props = {
  value: string;
  disabled?: boolean;
  onChange: (v: string) => void;
  onAsk: (questionOverride?: string) => void;
};

const SAMPLE_PROMPTS = [
  { text: "When should a client submit a grievance?", label: "Policy", color: "#38bdf8" },
  { text: "What happened with Nathan's drug screen in his April 14 session?", label: "Transcript", color: "#818cf8" },
  { text: "What are key themes Robert talks about across sessions?", label: "Summary", color: "#a78bfa" },
  { text: "Did the case manager follow check-in guidelines for Nathan?", label: "Cross-Source", color: "#f472b6" },
  { text: "Did Nathan attend his welding class?", label: "No-Evidence Test", color: "#fbbf24" },
];

export default function QuestionInput({ value, disabled, onChange, onAsk }: Props) {
  const handleSelectSample = (promptText: string) => {
    onChange(promptText);
    onAsk(promptText);
  };

  return (
    <section
      aria-label="Ask a question"
      style={{
        background: "#1e293b",
        border: "1px solid #334155",
        borderRadius: 12,
        padding: 20,
        marginBottom: 20,
        boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
      }}
    >
      <label htmlFor="q" style={{ display: "block", marginBottom: 10, fontWeight: 600, fontSize: 15, color: "#f1f5f9" }}>
        Ask a Question
      </label>
      <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
        <input
          id="q"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !disabled && value.trim()) onAsk();
          }}
          placeholder="e.g. When should a client submit a grievance?"
          disabled={disabled}
          aria-label="Question input"
          style={{
            flex: 1,
            padding: "12px 14px",
            borderRadius: 8,
            border: "1px solid #475569",
            background: "#0f172a",
            color: "#f8fafc",
            fontSize: 14,
            outline: "none",
            opacity: disabled ? 0.7 : 1,
            transition: "border-color 0.2s",
          }}
        />
        <button
          onClick={() => onAsk()}
          disabled={disabled || !value.trim()}
          aria-label="Ask"
          style={{
            padding: "12px 24px",
            borderRadius: 8,
            border: "none",
            background: disabled || !value.trim() ? "#475569" : "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",
            color: "#ffffff",
            cursor: disabled || !value.trim() ? "not-allowed" : "pointer",
            fontWeight: 600,
            fontSize: 14,
            boxShadow: disabled || !value.trim() ? "none" : "0 2px 10px rgba(99, 102, 241, 0.4)",
            transition: "transform 0.1s, opacity 0.2s",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          {disabled && <span className="spinner" />}
          {disabled ? "Searching…" : "Ask Question"}
        </button>
      </div>

      <div>
        <span style={{ fontSize: 12, color: "#94a3b8", display: "block", marginBottom: 8 }}>Suggested queries:</span>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {SAMPLE_PROMPTS.map((item, idx) => (
            <button
              key={idx}
              type="button"
              disabled={disabled}
              onClick={() => handleSelectSample(item.text)}
              style={{
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: 6,
                color: "#cbd5e1",
                padding: "6px 10px",
                fontSize: 12,
                cursor: disabled ? "not-allowed" : "pointer",
                textAlign: "left",
                transition: "all 0.15s ease",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span>{item.text}</span>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  padding: "1px 5px",
                  borderRadius: 4,
                  background: "rgba(255, 255, 255, 0.08)",
                  color: item.color,
                }}
              >
                {item.label}
              </span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}


