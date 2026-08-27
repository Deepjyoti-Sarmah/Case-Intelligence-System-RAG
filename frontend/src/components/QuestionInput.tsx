type Props = {
  value: string;
  disabled?: boolean;
  onChange: (v: string) => void;
  onAsk: () => void;
};

export default function QuestionInput({ value, disabled, onChange, onAsk }: Props) {
  return (
    <section
      aria-label="Ask a question"
      style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, marginBottom: 16, background: "#fff" }}
    >
      <label htmlFor="q" style={{ display: "block", marginBottom: 8, fontWeight: 600 }}>
        Ask a question
      </label>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          id="q"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !disabled) onAsk();
          }}
          placeholder="e.g. When should a client submit a grievance?"
          disabled={disabled}
          aria-label="Question input"
          style={{
            flex: 1,
            padding: "10px 12px",
            borderRadius: 6,
            border: "1px solid #ccc",
            fontSize: 14,
            opacity: disabled ? 0.7 : 1,
          }}
        />
        <button
          onClick={onAsk}
          disabled={disabled || !value.trim()}
          aria-label="Ask"
          style={{
            padding: "10px 18px",
            borderRadius: 6,
            border: "none",
            background: disabled || !value.trim() ? "#999" : "#111",
            color: "#fff",
            cursor: disabled || !value.trim() ? "not-allowed" : "pointer",
            fontWeight: 600,
            minWidth: 80,
          }}
        >
          {disabled ? "Asking…" : "Ask"}
        </button>
      </div>
    </section>
  );
}
