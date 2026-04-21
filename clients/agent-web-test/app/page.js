"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_AGENT_API_URL || "http://127.0.0.1:8100";

export default function HomePage() {
  const [message, setMessage] = useState("Show me OCI consumption by service for the last 7 days.");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [conversation, setConversation] = useState([]);
  const [streamingAnswer, setStreamingAnswer] = useState("");
  const [meta, setMeta] = useState(null);

  const streamInvokeUrl = useMemo(() => `${DEFAULT_API_URL}/agent/invoke/stream`, []);

  function processSseFrame(frame) {
    const lines = frame.split("\n");
    let eventName = "message";
    const dataParts = [];

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataParts.push(line.slice(5).trim());
      }
    }

    const dataText = dataParts.join("\n");
    let data = {};

    if (dataText) {
      try {
        data = JSON.parse(dataText);
      } catch (_parseError) {
        data = {};
      }
    }

    return { eventName, data };
  }

  async function onSubmit(event) {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage) {
      return;
    }

    setLoading(true);
    setError("");
    setMeta(null);
    setStreamingAnswer("");

    const history = conversation.map((item) => ({
      role: item.role,
      content: item.content,
    }));
    setConversation((previous) => [...previous, { role: "user", content: trimmedMessage }]);
    setMessage("");

    try {
      const response = await fetch(streamInvokeUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          message: trimmedMessage,
          history,
        }),
      });

      if (!response.ok) {
        const rawText = await response.text();
        throw new Error(rawText || `Request failed with status ${response.status}`);
      }

      if (!response.body) {
        throw new Error("Streaming response body is missing.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulatedAnswer = "";
      let finalAnswer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";

        for (const frame of frames) {
          const { eventName, data } = processSseFrame(frame);

          if (eventName === "token") {
            const token = data.text || "";
            accumulatedAnswer += token;
            setStreamingAnswer(accumulatedAnswer);
          } else if (eventName === "final") {
            finalAnswer = data.answer || accumulatedAnswer;
            setMeta({
              mcp_servers: data.mcp_servers || [],
              tool_count: data.tool_count ?? 0,
            });
          } else if (eventName === "error") {
            throw new Error(data.detail || "Unexpected error while streaming agent response.");
          }
        }
      }

      const assistantContent = finalAnswer || accumulatedAnswer;
      if (assistantContent) {
        setConversation((previous) => [
          ...previous,
          { role: "assistant", content: assistantContent },
        ]);
      }
      setStreamingAnswer("");
    } catch (err) {
      setError(err.message || "Unexpected error while calling agent API.");
      setStreamingAnswer("");
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
          <span className="label">Agent Stream API:</span>
          <code>{streamInvokeUrl}</code>
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

        {conversation.length > 0 ? (
          <div className="answerBlock">
            <h2>Conversation</h2>
            <div className="conversation">
              {conversation.map((item, index) => (
                <div
                  key={`${item.role}-${index}`}
                  className={`message message-${item.role}`}
                >
                  <div className="messageRole">{item.role}</div>
                  <div className="markdownBody">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {item.content}
                    </ReactMarkdown>
                  </div>
                </div>
              ))}
              {loading ? (
                <div className="message message-assistant">
                  <div className="messageRole">assistant</div>
                  <div className="markdownBody">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {streamingAnswer || "Thinking..."}
                    </ReactMarkdown>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}
