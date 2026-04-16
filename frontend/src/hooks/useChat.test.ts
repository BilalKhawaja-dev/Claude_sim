/**
 * Tests for useChat hook — SSE streaming chat.
 *
 * Validates: Requirements 1.2, 1.3, 1.7
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { useChat, parseSSEData } from "./useChat";

// --- Polyfills for jsdom ---
import { TextEncoder as NodeTextEncoder, TextDecoder as NodeTextDecoder } from "util";
if (typeof globalThis.TextEncoder === "undefined") {
  (globalThis as any).TextEncoder = NodeTextEncoder;
}
if (typeof globalThis.TextDecoder === "undefined") {
  (globalThis as any).TextDecoder = NodeTextDecoder;
}

// --- Mocks ---

// Mock auth module
jest.mock("@/lib/auth", () => ({
  authHeaders: () => ({ Authorization: "Bearer test-token" }),
}));

// Mock crypto.randomUUID
let uuidCounter = 0;
Object.defineProperty(global, "crypto", {
  value: {
    randomUUID: () => `uuid-${++uuidCounter}`,
  },
});

// Helper: create a mock reader that yields SSE chunks
function createMockReader(chunks: string[]) {
  const encoder = new TextEncoder();
  let index = 0;
  return {
    read: jest.fn(async () => {
      if (index < chunks.length) {
        const value = encoder.encode(chunks[index]);
        index++;
        return { done: false, value };
      }
      return { done: true, value: undefined };
    }),
  };
}

// Helper: mock a successful fetch with SSE body
function mockFetchSSE(chunks: string[], status = 200) {
  const reader = createMockReader(chunks);
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    body: { getReader: () => reader },
    text: async () => "error body",
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  uuidCounter = 0;
  global.fetch = jest.fn();
});

// --- parseSSEData unit tests ---

describe("parseSSEData", () => {
  it("parses valid SSE data line", () => {
    expect(parseSSEData('data: {"text":"hello"}')).toBe("hello");
  });

  it("returns null for [DONE] signal", () => {
    expect(parseSSEData("data: [DONE]")).toBeNull();
  });

  it("returns null for empty lines", () => {
    expect(parseSSEData("")).toBeNull();
    expect(parseSSEData("   ")).toBeNull();
  });

  it("returns null for non-data lines", () => {
    expect(parseSSEData("event: message")).toBeNull();
    expect(parseSSEData("id: 123")).toBeNull();
  });

  it("returns null for invalid JSON", () => {
    expect(parseSSEData("data: {invalid}")).toBeNull();
  });

  it("returns null when text field is missing", () => {
    expect(parseSSEData('data: {"other":"value"}')).toBeNull();
  });
});

// --- useChat hook tests ---

describe("useChat", () => {
  it("initializes with empty state", () => {
    const { result } = renderHook(() => useChat("conv-1"));

    expect(result.current.messages).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.error).toBeNull();
    expect(typeof result.current.sendMessage).toBe("function");
    expect(typeof result.current.retry).toBe("function");
  });

  it("sends a message and streams SSE response chunks", async () => {
    const sseChunks = [
      'data: {"text":"Hello"}\n\n',
      'data: {"text":" world"}\n\n',
      "data: [DONE]\n\n",
    ];
    mockFetchSSE(sseChunks);

    const { result } = renderHook(() => useChat("conv-1"));

    await act(async () => {
      await result.current.sendMessage("Hi there");
    });

    // Should have user message + assistant message
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[0].content).toBe("Hi there");
    expect(result.current.messages[1].role).toBe("assistant");
    expect(result.current.messages[1].content).toBe("Hello world");
    expect(result.current.isStreaming).toBe(false);
  });

  it("sends correct request payload with auth headers", async () => {
    mockFetchSSE(['data: {"text":"ok"}\n\n']);

    const { result } = renderHook(() => useChat("conv-42"));

    await act(async () => {
      await result.current.sendMessage("test message");
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/chat",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer test-token",
        }),
        body: JSON.stringify({
          message: "test message",
          conversation_id: "conv-42",
          model: "sonnet",
        }),
      })
    );
  });

  it("sets error on non-ok response", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: async () => "Internal Server Error",
    });

    const { result } = renderHook(() => useChat("conv-1"));

    await act(async () => {
      await result.current.sendMessage("fail");
    });

    expect(result.current.error).toBe("Internal Server Error");
    expect(result.current.isStreaming).toBe(false);
  });

  it("sets error when fetch throws (connection drop)", async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(
      new Error("Network error")
    );

    const { result } = renderHook(() => useChat("conv-1"));

    await act(async () => {
      await result.current.sendMessage("fail");
    });

    expect(result.current.error).toBe("Network error");
    expect(result.current.isStreaming).toBe(false);
  });

  it("retry resends the last message", async () => {
    // First call fails
    (global.fetch as jest.Mock).mockRejectedValueOnce(
      new Error("Connection lost")
    );

    const { result } = renderHook(() => useChat("conv-1"));

    await act(async () => {
      await result.current.sendMessage("retry me");
    });

    expect(result.current.error).toBe("Connection lost");

    // Retry succeeds
    mockFetchSSE(['data: {"text":"retried!"}\n\n']);

    await act(async () => {
      result.current.retry();
    });

    // Wait for the retry to complete
    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    expect(result.current.error).toBeNull();
    // Should have user + assistant messages from the retry
    const assistantMsgs = result.current.messages.filter(
      (m) => m.role === "assistant"
    );
    expect(assistantMsgs.length).toBeGreaterThanOrEqual(1);
    expect(assistantMsgs[assistantMsgs.length - 1].content).toBe("retried!");
  });

  it("handles SSE chunks split across stream reads", async () => {
    // Simulate a chunk being split across two reads
    const sseChunks = [
      'data: {"text":"He',
      'llo"}\ndata: {"text":" world"}\n\n',
    ];
    mockFetchSSE(sseChunks);

    const { result } = renderHook(() => useChat("conv-1"));

    await act(async () => {
      await result.current.sendMessage("test");
    });

    const assistant = result.current.messages.find(
      (m) => m.role === "assistant"
    );
    // "Hello" comes from the reassembled line, " world" from the second line
    expect(assistant?.content).toBe("Hello world");
  });

  it("sets error when response body is null", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: null,
      text: async () => "",
    });

    const { result } = renderHook(() => useChat("conv-1"));

    await act(async () => {
      await result.current.sendMessage("no body");
    });

    expect(result.current.error).toBe("No response body");
  });
});
