import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";

// jsdom doesn't implement scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

// --- Mocks ---

const mockSendMessage = jest.fn();
const mockRetry = jest.fn();

jest.mock("@/hooks/useChat", () => ({
  useChat: jest.fn(() => ({
    messages: [],
    sendMessage: mockSendMessage,
    isStreaming: false,
    error: null,
    retry: mockRetry,
  })),
}));

const mockIsAuthenticated = jest.fn(() => true);
const mockRedirectToLogin = jest.fn();
const mockHandleAuthCallback = jest.fn(async () => false);
const mockStartSilentRefresh = jest.fn();
const mockAuthHeaders = jest.fn(() => ({ Authorization: "Bearer test" }));

jest.mock("@/lib/auth", () => ({
  isAuthenticated: () => mockIsAuthenticated(),
  redirectToLogin: () => mockRedirectToLogin(),
  handleAuthCallback: () => mockHandleAuthCallback(),
  startSilentRefresh: () => mockStartSilentRefresh(),
  authHeaders: () => mockAuthHeaders(),
}));

import ChatPage from "./page";
import { useChat } from "@/hooks/useChat";

const mockedUseChat = useChat as jest.MockedFunction<typeof useChat>;

// Suppress fetch errors in tests
const originalFetch = global.fetch;

beforeEach(() => {
  jest.clearAllMocks();
  mockIsAuthenticated.mockReturnValue(true);
  mockHandleAuthCallback.mockResolvedValue(false);

  // Default: fetch returns empty conversations list
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => [],
  });
});

afterEach(() => {
  global.fetch = originalFetch;
});

describe("ChatPage", () => {
  it("renders the chat page layout after auth", async () => {
    await act(async () => {
      render(<ChatPage />);
    });

    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
    expect(screen.getByTestId("conversation-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("model-selector")).toBeInTheDocument();
    expect(screen.getByTestId("chat-thread")).toBeInTheDocument();
    expect(screen.getByTestId("chat-input-form")).toBeInTheDocument();
    expect(screen.getByTestId("image-upload")).toBeInTheDocument();
  });

  it("shows loading state before auth resolves", async () => {
    // Make handleAuthCallback hang
    let resolveAuth!: (v: boolean) => void;
    mockHandleAuthCallback.mockReturnValue(
      new Promise<boolean>((r) => {
        resolveAuth = r;
      })
    );
    mockIsAuthenticated.mockReturnValue(false);

    render(<ChatPage />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();

    await act(async () => {
      resolveAuth(true);
    });

    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
  });

  it("redirects to login when not authenticated", async () => {
    mockIsAuthenticated.mockReturnValue(false);
    mockHandleAuthCallback.mockResolvedValue(false);

    await act(async () => {
      render(<ChatPage />);
    });

    expect(mockRedirectToLogin).toHaveBeenCalled();
  });

  it("handles auth callback flow", async () => {
    mockHandleAuthCallback.mockResolvedValue(true);

    await act(async () => {
      render(<ChatPage />);
    });

    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
  });

  it("fetches conversations on mount", async () => {
    const convos = [
      { id: "c1", title: "Test Conv", updated_at: new Date().toISOString() },
    ];
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => convos,
    });

    await act(async () => {
      render(<ChatPage />);
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/conversations"),
        expect.objectContaining({ headers: expect.any(Object) })
      );
    });
  });

  it("creates a new conversation when new button is clicked", async () => {
    const newConv = {
      id: "new-1",
      title: null,
      updated_at: new Date().toISOString(),
    };
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => [] }) // initial fetch
      .mockResolvedValueOnce({ ok: true, json: async () => newConv }); // create

    await act(async () => {
      render(<ChatPage />);
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId("new-conversation-btn"));
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/conversations"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("shows error banner with retry when useChat has error", async () => {
    mockedUseChat.mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isStreaming: false,
      error: "Connection failed",
      retry: mockRetry,
    });

    await act(async () => {
      render(<ChatPage />);
    });

    expect(screen.getByTestId("error-banner")).toBeInTheDocument();
    expect(screen.getByText("Connection failed")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("retry-button"));
    expect(mockRetry).toHaveBeenCalled();
  });

  it("disables chat input when no active conversation", async () => {
    await act(async () => {
      render(<ChatPage />);
    });

    // No active conversation → input should be disabled
    expect(screen.getByTestId("chat-input")).toBeDisabled();
  });

  it("disables chat input while streaming", async () => {
    mockedUseChat.mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isStreaming: true,
      error: null,
      retry: mockRetry,
    });

    await act(async () => {
      render(<ChatPage />);
    });

    expect(screen.getByTestId("chat-input")).toBeDisabled();
  });

  it("model selector defaults to sonnet", async () => {
    await act(async () => {
      render(<ChatPage />);
    });

    const sonnetBtn = screen.getByTestId("model-option-sonnet");
    expect(sonnetBtn).toHaveAttribute("aria-checked", "true");
  });
});
