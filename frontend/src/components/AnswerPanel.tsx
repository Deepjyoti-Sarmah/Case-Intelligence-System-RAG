type Props = {
  answer: string;
};

export default function AnswerPanel({ answer }: Props) {
  return (
    <section
      aria-label="Answer"
      style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, marginBottom: 16, background: "#fff" }}
    >
      <h2 style={{ marginTop: 0, marginBottom: 8, fontSize: 18 }}>Answer</h2>
      <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.6, margin: 0 }}>{answer}</p>
    </section>
  );
}
