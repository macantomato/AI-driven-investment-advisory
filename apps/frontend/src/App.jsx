import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE;

export default function App() {
  const [health, setHealth] = useState(null);
  const [advice, setAdvice] = useState(null);
  const [loading, setLoading] = useState(false);
  const disclaimer = "Educational only — NOT financial advice.";

  async function getHealth() {
    setLoading(true);
    setAdvice(null);
    try {
      const res = await fetch(`${API_BASE}/health`);
      const json = await res.json();
      setHealth(json);
    } catch (e) {
      setHealth({ error: String(e) });
    } finally {
      setLoading(false);
    }
  }

  async function getAdvice() {
    setLoading(true);
    setHealth(null);
    try {
      const res = await fetch(`${API_BASE}/advice`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          risk: 3,
          universe: ["AAPL", "MSFT", "JNJ"],
        }),
      });
      const json = await res.json();
      setAdvice(json);
    } catch (e) {
      setAdvice({ error: String(e) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: 860, margin: "40px auto", padding: 16 }}>
      <h1>AI-Driven Investment Advisor (Educational)</h1>
      <p style={{ marginTop: 4, opacity: 0.8 }}>
        <strong>Disclaimer:</strong> {disclaimer}
      </p>

      <div style={{ display: "flex", gap: 12, marginTop: 24 }}>
        <button onClick={getHealth} disabled={loading}>
          {loading ? "Loading..." : "Health"}
        </button>
        <button onClick={getAdvice} disabled={loading}>
          {loading ? "Loading..." : "Get Advice"}
        </button>
      </div>

      <div style={{ marginTop: 24 }}>
        {health && (
          <>
            <h3>/health result</h3>
            <pre style={{ background: "#111", color: "#0f0", padding: 12, borderRadius: 8 }}>
{JSON.stringify(health, null, 2)}
            </pre>
          </>
        )}
        {advice && (
          <>
            <h3>/advice result</h3>
            <pre style={{ background: "#111", color: "#0ff", padding: 12, borderRadius: 8 }}>
{JSON.stringify(advice, null, 2)}
            </pre>
          </>
        )}
      </div>

      <footer style={{ marginTop: 32, fontSize: 12, opacity: 0.7 }}>
        UI and API are strictly for education. {disclaimer}
      </footer>
    </div>
  );
}
