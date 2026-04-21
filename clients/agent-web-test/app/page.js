"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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
  const messageListRef = useRef(null);

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

  useEffect(() => {
    if (!messageListRef.current) {
      return;
    }
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
  }, [conversation, streamingAnswer, loading]);

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

  function onClearConversation() {
    setConversation([]);
    setStreamingAnswer("");
    setMeta(null);
    setError("");
  }

  function onComposerKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!loading && message.trim()) {
        event.currentTarget.form?.requestSubmit();
      }
    }
  }

  return (
    <main className="chatLayout">
      <aside className="sidebar">
        <h1>OCI Consumption Chat</h1>
        <p className="sidebarSubtitle">
          Tool-calling assistant for OCI consumption analysis.
        </p>

        <div className="metaCard">
          <h2>Connection</h2>
          <p className="label">Stream Endpoint</p>
          <code className="endpoint">{streamInvokeUrl}</code>
        </div>

        <div className="metaCard">
          <h2>Metadata</h2>
          <p>
            <strong>Servers:</strong> {meta?.mcp_servers?.join(", ") || "-"}
          </p>
          <p>
            <strong>Tools loaded:</strong> {meta?.tool_count ?? "-"}
          </p>
          <p>
            <strong>Messages:</strong> {conversation.length}
          </p>
        </div>

        <div className="sidebarActions">
          <button
            type="button"
            className="secondaryButton"
            onClick={onClearConversation}
            disabled={loading || conversation.length === 0}
          >
            Clear Conversation
          </button>
        </div>
      </aside>

      <section className="chatPanel">
        <div className="messageList" ref={messageListRef}>
          {conversation.length === 0 ? (
            <div className="emptyState">
              Start a conversation by asking about OCI consumption.
            </div>
          ) : null}

          {conversation.map((item, index) => (
            <div
              key={`${item.role}-${index}`}
              className={`messageRow ${item.role === "user" ? "userRow" : "assistantRow"}`}
            >
              <div className={`bubble ${item.role === "user" ? "userBubble" : "assistantBubble"}`}>
                <div className="messageRole">{item.role}</div>
                {item.role === "assistant" ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {item.content}
                  </ReactMarkdown>
                ) : (
                  <p>{item.content}</p>
                )}
              </div>
            </div>
          ))}

          {loading ? (
            <div className="messageRow assistantRow">
              <div className="bubble assistantBubble">
                <div className="messageRole">assistant</div>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {streamingAnswer || "Thinking..."}
                </ReactMarkdown>
              </div>
            </div>
          ) : null}
        </div>

        {error ? <div className="error">{error}</div> : null}

        <form onSubmit={onSubmit} className="composer">
          <textarea
            id="message"
            rows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={onComposerKeyDown}
            placeholder="Ask something about OCI consumption..."
            required
          />
          <button type="submit" disabled={loading || !message.trim()}>
            {loading ? "Invoking..." : "Send"}
          </button>
        </form>
      </section>
    </main>
  );
}
