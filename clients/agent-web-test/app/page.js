"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_AGENT_API_URL || "http://127.0.0.1:8100";

export default function HomePage() {
  const [message, setMessage] = useState("Show me OCI consumption by service for the last 7 days.");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [answer, setAnswer] = useState("");
  const [meta, setMeta] = useState(null);

  const invokeUrl = useMemo(() => `${DEFAULT_API_URL}/agent/invoke`, []);

  async function onSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setAnswer("");
    setMeta(null);

    try {
      const response = await fetch(invokeUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || `Request failed with status ${response.status}`);
      }

      setAnswer(data.answer || "");
      setMeta({
        mcp_servers: data.mcp_servers || [],
        tool_count: data.tool_count ?? 0,
      });
    } catch (err) {
      setError(err.message || "Unexpected error while calling agent API.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <section className="card">
        <h1>OCI Consumption Agent - Web Test Client</h1>
        <p className="subtitle">Use this page to call the FastAPI agent endpoint and validate tool-calling behavior.</p>

        <div className="metaRow">
          <span className="label">Agent API:</span>
          <code>{invokeUrl}</code>
        </div>

        <form onSubmit={onSubmit} className="form">
          <label htmlFor="message">Prompt</label>
          <textarea
            id="message"
            rows={6}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ask something about OCI consumption..."
            required
          />

          <button type="submit" disabled={loading || !message.trim()}>
            {loading ? "Invoking agent..." : "Invoke Agent"}
          </button>
        </form>

        {error ? <div className="error">{error}</div> : null}

        {meta ? (
          <div className="metaBlock">
            <h2>Execution Metadata</h2>
            <p>
              <strong>Servers:</strong> {meta.mcp_servers.join(", ") || "-"}
            </p>
            <p>
              <strong>Tools loaded:</strong> {meta.tool_count}
            </p>
          </div>
        ) : null}

        {answer ? (
          <div className="answerBlock">
            <h2>Assistant Answer</h2>
            <div className="markdownBody">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}
