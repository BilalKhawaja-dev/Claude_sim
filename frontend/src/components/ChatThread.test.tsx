import React from "react";
import { render, screen } from "@testing-library/react";
import ChatThread from "./ChatThread";
import type { Message } from "@/hooks/useChat";

// Mock scrollIntoView
const scrollIntoViewMock = jest.fn();
window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock;

function makeMsg(overrides: Partial<Message> & { id: string; role: Message["role"] }): Message {
  return {
    content: "",
    has_image: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("ChatThread", () => {
  it("renders all messages", () => {
    const messages: Message[] = [
      makeMsg({ id: "1", role: "user", content: "Hello" }),
      makeMsg({ id: "2", role: "assistant", content: "Hi there" }),
    ];

    render(<ChatThread messages={messages} isStreaming={false} />);

    expect(screen.getByTestId("message-1")).toBeInTheDocument();
    expect(screen.getByTestId("message-2")).toBeInTheDocument();
  });

  it("renders empty state with no messages", () => {
    render(<ChatThread messages={[]} isStreaming={false} />);

    const thread = screen.getByTestId("chat-thread");
    // Only the scroll anchor div should be present
    expect(thread.children).toHaveLength(1);
  });

  it("shows typing indicator only on last assistant message when streaming", () => {
    const messages: Message[] = [
      makeMsg({ id: "1", role: "user", content: "Hello" }),
      makeMsg({ id: "2", role: "assistant", content: "Hi" }),
    ];

    render(<ChatThread messages={messages} isStreaming={true} />);

    expect(screen.getByTestId("typing-indicator")).toBeInTheDocument();
  });

  it("does not show typing indicator when not streaming", () => {
    const messages: Message[] = [
      makeMsg({ id: "1", role: "user", content: "Hello" }),
      makeMsg({ id: "2", role: "assistant", content: "Hi" }),
    ];

    render(<ChatThread messages={messages} isStreaming={false} />);

    expect(screen.queryByTestId("typing-indicator")).not.toBeInTheDocument();
  });

  it("does not show typing indicator if last message is from user", () => {
    const messages: Message[] = [
      makeMsg({ id: "1", role: "assistant", content: "Hi" }),
      makeMsg({ id: "2", role: "user", content: "Hello" }),
    ];

    render(<ChatThread messages={messages} isStreaming={true} />);

    expect(screen.queryByTestId("typing-indicator")).not.toBeInTheDocument();
  });

  it("auto-scrolls to bottom when messages change", () => {
    const messages: Message[] = [
      makeMsg({ id: "1", role: "user", content: "Hello" }),
    ];

    const { rerender } = render(<ChatThread messages={messages} isStreaming={false} />);

    scrollIntoViewMock.mockClear();

    const updated = [
      ...messages,
      makeMsg({ id: "2", role: "assistant", content: "Hi" }),
    ];
    rerender(<ChatThread messages={updated} isStreaming={false} />);

    expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: "smooth" });
  });

  it("has accessible role=log and aria-live", () => {
    render(<ChatThread messages={[]} isStreaming={false} />);

    const thread = screen.getByTestId("chat-thread");
    expect(thread).toHaveAttribute("role", "log");
    expect(thread).toHaveAttribute("aria-live", "polite");
  });
});
