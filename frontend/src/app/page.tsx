"use client";

/**
 * ChatPage — main layout wiring ConversationSidebar, ChatThread,
 * ChatInput, ModelSelector, and ImageUpload together.
 *
 * Validates: Requirements 1.1, 2.1, 3.1
 */

import React, { useEffect, useState, useCallback } from "react";
import ConversationSidebar, {
  type ConversationSummary,
} from "@/components/ConversationSidebar";
import ChatThread from "@/components/ChatThread";
import ChatInput from "@/components/ChatInput";
import ModelSelector from "@/components/ModelSelector";
import ImageUpload from "@/components/ImageUpload";
import { useChat } from "@/hooks/useChat";
import {
  isAuthenticated,
  redirectToLogin,
  handleAuthCallback,
  authHeaders,
  startSilentRefresh,
} from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

const IMAGE_FORMATS = [
  "image/png",
  "image/jpeg",
  "image/gif",
  "image/webp",
];

const styles = {
  wrapper: {
    display: "flex",
    height: "100vh",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  } as React.CSSProperties,
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
  } as React.CSSProperties,
  topBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "8px 16px",
    borderBottom: "1px solid #e5e7eb",
  } as React.CSSProperties,
  bottomBar: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "0 16px 8px",
  } as React.CSSProperties,
  errorBanner: {
    padding: "8px 16px",
    backgroundColor: "#fef2f2",
    color: "#dc2626",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    fontSize: 14,
  } as React.CSSProperties,
  retryBtn: {
    padding: "4px 12px",
    borderRadius: 6,
    border: "1px solid #dc2626",
    backgroundColor: "transparent",
    color: "#dc2626",
    cursor: "pointer",
    fontSize: 13,
  } as React.CSSProperties,
};

export default function ChatPage() {
  const [authReady, setAuthReady] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [model, setModel] = useState<"sonnet" | "opus">("sonnet");
  const [pendingImage, setPendingImage] = useState<File | undefined>(undefined);

  const { messages, sendMessage, isStreaming, error, retry } = useChat(
    activeId ?? ""
  );

  // --- Auth: check on mount, handle callback ---
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const wasCallback = await handleAuthCallback();
      if (!cancelled) {
        if (wasCallback || isAuthenticated()) {
          if (!wasCallback) startSilentRefresh();
          setAuthReady(true);
        } else {
          // Dev mode: skip auth if NEXT_PUBLIC_SKIP_AUTH is set
          if (process.env.NEXT_PUBLIC_SKIP_AUTH === "true") {
            setAuthReady(true);
          } else {
            redirectToLogin();
          }
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // --- Fetch conversations once auth is ready ---
  useEffect(() => {
    if (!authReady) return;
    fetchConversations();
  }, [authReady]);

  const fetchConversations = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/conversations`, {
        headers: authHeaders(),
      });
      if (res.ok) {
        const data: ConversationSummary[] = await res.json();
        setConversations(data);
      }
    } catch {
      // silently ignore — sidebar will be empty
    }
  }, []);

  // --- Conversation actions ---
  const handleNewConversation = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
      });
      if (res.ok) {
        const conv: ConversationSummary = await res.json();
        setConversations((prev) => [conv, ...prev]);
        setActiveId(conv.id);
      }
    } catch {
      // ignore
    }
  }, []);

  const handleSelectConversation = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const handleDeleteConversation = useCallback(
    async (id: string) => {
      try {
        await fetch(`${API_BASE}/api/conversations/${id}`, {
          method: "DELETE",
          headers: authHeaders(),
        });
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (activeId === id) setActiveId(null);
      } catch {
        // ignore
      }
    },
    [activeId]
  );

  // --- Send message with model + optional image ---
  const handleSend = useCallback(
    (text: string) => {
      if (!activeId) return;
      sendMessage(text, pendingImage);
      setPendingImage(undefined);
    },
    [activeId, sendMessage, pendingImage]
  );

  const handleImageUpload = useCallback((file: File) => {
    setPendingImage(file);
  }, []);

  // --- Loading state ---
  if (!authReady) {
    return (
      <main style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        <p>Loading…</p>
      </main>
    );
  }

  return (
    <div data-testid="chat-page" style={styles.wrapper}>
      <ConversationSidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelectConversation}
        onDelete={handleDeleteConversation}
        onNew={handleNewConversation}
      />

      <main style={styles.main}>
        <div style={styles.topBar}>
          <ModelSelector currentModel={model} onChange={setModel} />
        </div>

        <ChatThread messages={messages} isStreaming={isStreaming} />

        {error && (
          <div data-testid="error-banner" style={styles.errorBanner}>
            <span>{error}</span>
            <button
              data-testid="retry-button"
              style={styles.retryBtn}
              onClick={retry}
            >
              Retry
            </button>
          </div>
        )}

        <div style={styles.bottomBar}>
          <ImageUpload
            onUpload={handleImageUpload}
            maxSizeMB={5}
            acceptedFormats={IMAGE_FORMATS}
          />
        </div>

        <ChatInput onSend={handleSend} disabled={isStreaming || !activeId} />
      </main>
    </div>
  );
}
