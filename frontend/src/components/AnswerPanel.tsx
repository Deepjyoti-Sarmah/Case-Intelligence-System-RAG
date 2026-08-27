type Props = {
  answer: string;
  groundingStatus?: "SUPPORTED" | "PARTIALLY_SUPPORTED" | "NO_EVIDENCE";
};

export default function AnswerPanel({ answer, groundingStatus = "SUPPORTED" }: Props) {
  const badgeConfig = {
    SUPPORTED: { bg: "rgba(16, 185, 129, 0.15)", text: "#10b981", border: "rgba(16, 185, 129, 0.3)", label: "Grounded Evidence" },
    PARTIALLY_SUPPORTED: { bg: "rgba(245, 158, 11, 0.15)", text: "#f59e0b", border: "rgba(245, 158, 11, 0.3)", label: "Partially Grounded" },
    NO_EVIDENCE: { bg: "rgba(239, 68, 68, 0.15)", text: "#ef4444", border: "rgba(239, 68, 68, 0.3)", label: "No Evidence Found" },
  }[groundingStatus];

  return (
    <section
      aria-label="Answer"
      style={{
        background: "#1e293b",
        border: "1px solid #334155",
        borderRadius: 12,
        padding: 20,
        marginBottom: 20,
        boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: "#f8fafc" }}>Generated Answer</h2>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: 0.5,
            padding: "4px 10px",
            borderRadius: 20,
            background: badgeConfig.bg,
            color: badgeConfig.text,
            border: `1px solid ${badgeConfig.border}`,
            textTransform: "uppercase",
          }}
        >
          {badgeConfig.label}
        </span>
      </div>
      <div
        style={{
          whiteSpace: "pre-wrap",
          lineHeight: 1.7,
          fontSize: 15,
          color: "#e2e8f0",
          background: "#0f172a",
          padding: 16,
          borderRadius: 8,
          border: "1px solid #334155",
        }}
      >
        {answer}
      </div>
    </section>
  );
}

