/**
 * ChatInput — text input with send button for composing chat messages.
 *
 * Supports Enter to send, Shift+Enter for newline.
 * Disabled while streaming to prevent concurrent sends.
 *
 * Validates: Requirements 1.1
 */

import React, { useState, useCallback, useRef } from "react";

export interface ChatInputProps {
  onSend: (text: string, image?: File) => void;
  disabled: boolean;
}

const styles = {
  form: {
    display: "flex",
    gap: 8,
    padding: "12px 16px",
    borderTop: "1px solid #e5e7eb",
    alignItems: "flex-end",
  } as React.CSSProperties,
  textarea: {
    flex: 1,
    resize: "none" as const,
    padding: "10px 12px",
    borderRadius: 8,
    border: "1px solid #d1d5db",
    fontSize: 14,
    lineHeight: 1.5,
    fontFamily: "inherit",
    minHeight: 42,
    maxHeight: 160,
    outline: "none",
  } as React.CSSProperties,
  button: (disabled: boolean): React.CSSProperties => ({
    padding: "10px 20px",
    borderRadius: 8,
    border: "none",
    backgroundColor: disabled ? "#9ca3af" : "#2563eb",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
  }),
};

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }, [text, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return (
    <form
      data-testid="chat-input-form"
      style={styles.form}
      onSubmit={(e) => {
        e.preventDefault();
        handleSend();
      }}
    >
      <label htmlFor="chat-input" className="sr-only" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0,0,0,0)" }}>
        Type a message
      </label>
      <textarea
        id="chat-input"
        ref={textareaRef}
        data-testid="chat-input"
        style={styles.textarea}
        placeholder="Type a message…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={1}
        aria-label="Type a message"
      />
      <button
        type="submit"
        data-testid="send-button"
        style={styles.button(disabled || !text.trim())}
        disabled={disabled || !text.trim()}
        aria-label="Send message"
      >
        Send
      </button>
    </form>
  );
}
