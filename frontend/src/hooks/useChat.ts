/**
 * useChat hook — SSE streaming chat with the backend.
 *
 * Uses fetch + ReadableStream to POST /api/chat and parse SSE events,
 * since standard EventSource only supports GET.
 *
 * Validates: Requirements 1.2, 1.3, 1.7
 */

import { useState, useCallback, useRef } from "react";
import { authHeaders } from "@/lib/auth";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  has_image: boolean;
  created_at: string;
}

interface UseChatReturn {
  messages: Message[];
  sendMessage: (text: string, image?: File) => Promise<void>;
  isStreaming: boolean;
  error: string | null;
  retry: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

/** Parse a single SSE line of the form `data: {...}\n` */
export function parseSSEData(line: string): string | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data: ")) return null;
  const json = trimmed.slice(6);
  if (json === "[DONE]") return null;
  try {
    const parsed = JSON.parse(json);
    return typeof parsed.text === "string" ? parsed.text : null;
  } catch {
    return null;
  }
}

export function useChat(conversationId: string): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastRequestRef = useRef<{ text: string; image?: File } | null>(null);

  const sendMessage = useCallback(
    async (text: string, image?: File) => {
      lastRequestRef.current = { text, image };
      setError(null);
      setIsStreaming(true);

      // Add user message optimistically
      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        has_image: !!image,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      // Prepare assistant placeholder
      const assistantId = crypto.randomUUID();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        has_image: false,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        let imageBase64: string | undefined;
        if (image) {
          imageBase64 = await fileToBase64(image);
        }

        const res = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...authHeaders(),
          },
          body: JSON.stringify({
            message: text,
            conversation_id: conversationId,
            model: "sonnet",
            ...(imageBase64 ? { image: imageBase64 } : {}),
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const errBody = await res.text();
          throw new Error(errBody || `Request failed: ${res.status}`);
        }

        if (!res.body) {
          throw new Error("No response body");
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          // Keep the last incomplete line in the buffer
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            const chunk = parseSSEData(line);
            if (chunk !== null) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + chunk }
                    : m
                )
              );
            }
          }
        }

        // Process any remaining buffer
        if (buffer.trim()) {
          const chunk = parseSSEData(buffer);
          if (chunk !== null) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + chunk }
                  : m
              )
            );
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return; // User-initiated abort, not an error
        }
        const message =
          err instanceof Error ? err.message : "Connection failed";
        setError(message);
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [conversationId]
  );

  const retry = useCallback(() => {
    if (lastRequestRef.current) {
      // Remove the failed assistant message (last message)
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.content === "") {
          return prev.slice(0, -2); // Remove both user + empty assistant
        }
        return prev.slice(0, -1); // Remove just the last message
      });
      const { text, image } = lastRequestRef.current;
      sendMessage(text, image);
    }
  }, [sendMessage]);

  return { messages, sendMessage, isStreaming, error, retry };
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip the data URL prefix (e.g. "data:image/png;base64,")
      const base64 = result.split(",")[1] ?? result;
      resolve(base64);
    };
    reader.onerror = () => reject(new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}
