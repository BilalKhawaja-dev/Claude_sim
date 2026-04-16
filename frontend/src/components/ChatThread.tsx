/**
 * ChatThread — renders a scrollable list of MessageBubble components.
 *
 * Auto-scrolls to the bottom when new messages arrive or during streaming.
 * Shows a typing indicator on the last assistant message when isStreaming is true.
 *
 * Validates: Requirements 1.3, 1.4, 8.4, 9.3
 */

import React, { useEffect, useRef } from "react";
import type { Message } from "@/hooks/useChat";
import MessageBubble from "./MessageBubble";

export interface ChatThreadProps {
  messages: Message[];
  isStreaming: boolean;
}

const containerStyle: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: "16px 0",
  display: "flex",
  flexDirection: "column",
  gap: 4,
};

export default function ChatThread({ messages, isStreaming }: ChatThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  return (
    <div data-testid="chat-thread" style={containerStyle} role="log" aria-live="polite">
      {messages.map((msg, idx) => {
        const isLast = idx === messages.length - 1;
        const showTyping = isStreaming && isLast && msg.role === "assistant";

        return (
          <MessageBubble
            key={msg.id}
            message={msg}
            isStreaming={showTyping}
          />
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
