/**
 * MessageBubble — renders a single chat message.
 *
 * User messages are right-aligned, assistant messages left-aligned.
 * Shows a typing indicator on the last assistant message when streaming.
 * Displays images inline when has_image is true.
 *
 * Validates: Requirements 1.3, 1.4, 8.4, 9.3
 */

import React from "react";
import type { Message } from "@/hooks/useChat";

export interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
}

const styles = {
  wrapper: (isUser: boolean): React.CSSProperties => ({
    display: "flex",
    justifyContent: isUser ? "flex-end" : "flex-start",
    padding: "4px 16px",
  }),
  bubble: (isUser: boolean): React.CSSProperties => ({
    maxWidth: "70%",
    padding: "10px 14px",
    borderRadius: 12,
    backgroundColor: isUser ? "#2563eb" : "#f3f4f6",
    color: isUser ? "#fff" : "#1f2937",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontSize: 14,
    lineHeight: 1.5,
  }),
  image: {
    maxWidth: "100%",
    borderRadius: 8,
    marginTop: 8,
  } as React.CSSProperties,
  typingDots: {
    display: "inline-flex",
    gap: 4,
    padding: "4px 0",
  } as React.CSSProperties,
  dot: (delay: number): React.CSSProperties => ({
    width: 6,
    height: 6,
    borderRadius: "50%",
    backgroundColor: "#9ca3af",
    animation: "typing-bounce 1.2s infinite",
    animationDelay: `${delay}s`,
  }),
};

export function TypingIndicator() {
  return (
    <span data-testid="typing-indicator" style={styles.typingDots}>
      <span style={styles.dot(0)} />
      <span style={styles.dot(0.2)} />
      <span style={styles.dot(0.4)} />
    </span>
  );
}

export default function MessageBubble({ message, isStreaming }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div data-testid={`message-${message.id}`} style={styles.wrapper(isUser)}>
      <div style={styles.bubble(isUser)}>
        {message.content}

        {message.has_image && message.role === "user" && (
          <img
            src={`data:image/png;base64,${(message as MessageWithImage).image_data ?? ""}`}
            alt="Uploaded image"
            style={styles.image}
            data-testid="inline-image"
          />
        )}

        {message.has_image && message.role === "assistant" && (
          <img
            src={`data:image/png;base64,${(message as MessageWithImage).image_data ?? ""}`}
            alt="Generated image"
            style={styles.image}
            data-testid="inline-image"
          />
        )}

        {isStreaming && !isUser && <TypingIndicator />}
      </div>
    </div>
  );
}

/** Extended message type that may carry image_data */
interface MessageWithImage extends Message {
  image_data?: string;
}
