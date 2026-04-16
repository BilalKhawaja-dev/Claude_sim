import React from "react";
import { render, screen } from "@testing-library/react";
import MessageBubble from "./MessageBubble";
import type { Message } from "@/hooks/useChat";

function makeMsg(overrides: Partial<Message> & { id: string; role: Message["role"] }): Message {
  return {
    content: "",
    has_image: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("MessageBubble", () => {
  it("renders user message content", () => {
    const msg = makeMsg({ id: "u1", role: "user", content: "Hello world" });
    render(<MessageBubble message={msg} />);

    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders assistant message content", () => {
    const msg = makeMsg({ id: "a1", role: "assistant", content: "Hi there" });
    render(<MessageBubble message={msg} />);

    expect(screen.getByText("Hi there")).toBeInTheDocument();
  });

  it("right-aligns user messages", () => {
    const msg = makeMsg({ id: "u1", role: "user", content: "Test" });
    render(<MessageBubble message={msg} />);

    const wrapper = screen.getByTestId("message-u1");
    expect(wrapper.style.justifyContent).toBe("flex-end");
  });

  it("left-aligns assistant messages", () => {
    const msg = makeMsg({ id: "a1", role: "assistant", content: "Test" });
    render(<MessageBubble message={msg} />);

    const wrapper = screen.getByTestId("message-a1");
    expect(wrapper.style.justifyContent).toBe("flex-start");
  });

  it("shows typing indicator when isStreaming is true on assistant message", () => {
    const msg = makeMsg({ id: "a1", role: "assistant", content: "" });
    render(<MessageBubble message={msg} isStreaming={true} />);

    expect(screen.getByTestId("typing-indicator")).toBeInTheDocument();
  });

  it("does not show typing indicator when isStreaming is false", () => {
    const msg = makeMsg({ id: "a1", role: "assistant", content: "Done" });
    render(<MessageBubble message={msg} isStreaming={false} />);

    expect(screen.queryByTestId("typing-indicator")).not.toBeInTheDocument();
  });

  it("does not show typing indicator on user messages even when isStreaming", () => {
    const msg = makeMsg({ id: "u1", role: "user", content: "Hello" });
    render(<MessageBubble message={msg} isStreaming={true} />);

    expect(screen.queryByTestId("typing-indicator")).not.toBeInTheDocument();
  });

  it("displays inline image when has_image is true for user message", () => {
    const msg = {
      ...makeMsg({ id: "u1", role: "user" as const, content: "Look at this", has_image: true }),
      image_data: "iVBORw0KGgo=",
    };
    render(<MessageBubble message={msg} />);

    const img = screen.getByTestId("inline-image");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "data:image/png;base64,iVBORw0KGgo=");
  });

  it("displays inline image for assistant generated images", () => {
    const msg = {
      ...makeMsg({ id: "a1", role: "assistant" as const, content: "Here is your image", has_image: true }),
      image_data: "AAAA",
    };
    render(<MessageBubble message={msg} />);

    const img = screen.getByTestId("inline-image");
    expect(img).toBeInTheDocument();
  });

  it("does not display image when has_image is false", () => {
    const msg = makeMsg({ id: "u1", role: "user", content: "No image" });
    render(<MessageBubble message={msg} />);

    expect(screen.queryByTestId("inline-image")).not.toBeInTheDocument();
  });
});
