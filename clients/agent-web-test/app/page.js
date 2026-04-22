"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_AGENT_API_URL || "http://127.0.0.1:8100";
const DEFAULT_STREAM_URL = `${DEFAULT_API_URL}/agent/invoke/stream`;

export default function HomePage() {
  const [agentUrl, setAgentUrl] = useState(DEFAULT_STREAM_URL);
  const [darkMode, setDarkMode] = useState(false);
  const [message, setMessage] = useState("Show me OCI consumption by service for the last 7 days.");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [conversation, setConversation] = useState([]);
  const [streamingAnswer, setStreamingAnswer] = useState("");
  const [meta, setMeta] = useState(null);
  const [mcpStatuses, setMcpStatuses] = useState([]);
  const messageListRef = useRef(null);

  const streamInvokeUrl = useMemo(() => {
    const trimmed = agentUrl.trim();
    if (!trimmed) {
      return DEFAULT_STREAM_URL;
    }
    return trimmed.replace(/\/+$/, "");
  }, [agentUrl]);
  const mcpServerConfigUrl = useMemo(() => {
    if (streamInvokeUrl.endsWith("/agent/invoke/stream")) {
      return `${streamInvokeUrl.slice(0, -"/agent/invoke/stream".length)}/agent/mcp-servers`;
    }
    return `${DEFAULT_API_URL}/agent/mcp-servers`;
  }, [streamInvokeUrl]);
  const displayedMcpServers = useMemo(
    () =>
      meta?.mcp_server_statuses?.length
        ? meta.mcp_server_statuses
        : mcpStatuses,
    [meta, mcpStatuses]
  );

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

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("ui-theme");
    if (savedTheme === "dark") {
      setDarkMode(true);
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "light");
    window.localStorage.setItem("ui-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    let cancelled = false;

    async function loadMcpServerStatuses() {
      try {
        const response = await fetch(mcpServerConfigUrl);
        if (!response.ok) {
          return;
        }
        const data = await response.json();
        if (!cancelled && Array.isArray(data)) {
          setMcpStatuses(data);
        }
      } catch (_error) {
        // Keep UI resilient when backend metadata endpoint is unavailable.
      }
    }

    loadMcpServerStatuses();
    return () => {
      cancelled = true;
    };
  }, [mcpServerConfigUrl]);

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
            const statuses = Array.isArray(data.mcp_server_statuses)
              ? data.mcp_server_statuses
              : [];
            if (statuses.length) {
              setMcpStatuses(statuses);
            }
            setMeta({
              mcp_servers: data.mcp_servers || [],
              mcp_server_statuses: statuses,
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
          <label className="label" htmlFor="agent-url">
            AGENT_URL
          </label>
          <input
            id="agent-url"
            className="endpointInput"
            type="text"
            value={agentUrl}
            onChange={(event) => setAgentUrl(event.target.value)}
            placeholder="http://127.0.0.1:8100/agent/invoke/stream"
          />
        </div>

        <div className="metaCard">
          <h2>Appearance</h2>
          <label className="toggleRow" htmlFor="dark-mode-toggle">
            <span>Dark mode</span>
            <input
              id="dark-mode-toggle"
              type="checkbox"
              checked={darkMode}
              onChange={(event) => setDarkMode(event.target.checked)}
            />
          </label>
        </div>

        <div className="metaCard">
          <h2>MCP Servers</h2>
          <div className="serverList">
            {displayedMcpServers.length === 0 ? <p>-</p> : null}
            {displayedMcpServers.map((server) => (
              <span
                key={server.name}
                className={`serverBadge ${server.enabled ? "enabled" : "disabled"}`}
              >
                {server.name}
              </span>
            ))}
          </div>
        </div>

        <div className="metaCard">
          <h2>Metadata</h2>
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
