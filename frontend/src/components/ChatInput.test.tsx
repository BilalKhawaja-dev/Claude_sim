import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ChatInput from "./ChatInput";

describe("ChatInput", () => {
  it("renders textarea and send button", () => {
    render(<ChatInput onSend={jest.fn()} disabled={false} />);

    expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    expect(screen.getByTestId("send-button")).toBeInTheDocument();
  });

  it("calls onSend with trimmed text when send button is clicked", async () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} disabled={false} />);

    const textarea = screen.getByTestId("chat-input");
    fireEvent.change(textarea, { target: { value: "  Hello world  " } });
    fireEvent.click(screen.getByTestId("send-button"));

    expect(onSend).toHaveBeenCalledWith("Hello world");
  });

  it("clears input after sending", () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} disabled={false} />);

    const textarea = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "Hello" } });
    fireEvent.click(screen.getByTestId("send-button"));

    expect(textarea.value).toBe("");
  });

  it("sends on Enter key press", () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} disabled={false} />);

    const textarea = screen.getByTestId("chat-input");
    fireEvent.change(textarea, { target: { value: "Hello" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    expect(onSend).toHaveBeenCalledWith("Hello");
  });

  it("does not send on Shift+Enter (allows newline)", () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} disabled={false} />);

    const textarea = screen.getByTestId("chat-input");
    fireEvent.change(textarea, { target: { value: "Hello" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });

    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables textarea and button when disabled prop is true", () => {
    render(<ChatInput onSend={jest.fn()} disabled={true} />);

    expect(screen.getByTestId("chat-input")).toBeDisabled();
    expect(screen.getByTestId("send-button")).toBeDisabled();
  });

  it("does not send when disabled even with text", () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} disabled={true} />);

    const textarea = screen.getByTestId("chat-input");
    // Can't type when disabled, but test the guard
    fireEvent.change(textarea, { target: { value: "Hello" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not send empty or whitespace-only messages", () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} disabled={false} />);

    const textarea = screen.getByTestId("chat-input");
    fireEvent.change(textarea, { target: { value: "   " } });
    fireEvent.click(screen.getByTestId("send-button"));

    expect(onSend).not.toHaveBeenCalled();
  });

  it("send button is disabled when input is empty", () => {
    render(<ChatInput onSend={jest.fn()} disabled={false} />);

    expect(screen.getByTestId("send-button")).toBeDisabled();
  });

  it("has accessible labels", () => {
    render(<ChatInput onSend={jest.fn()} disabled={false} />);

    expect(screen.getByLabelText("Type a message")).toBeInTheDocument();
    expect(screen.getByLabelText("Send message")).toBeInTheDocument();
  });
});
