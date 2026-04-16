import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ConversationSidebar, {
  formatRelativeTime,
  filterAndSort,
  type ConversationSummary,
} from "./ConversationSidebar";

function makeConv(overrides: Partial<ConversationSummary> & { id: string }): ConversationSummary {
  return {
    title: "Test conversation",
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("formatRelativeTime", () => {
  it('returns "just now" for recent timestamps', () => {
    expect(formatRelativeTime(new Date().toISOString())).toBe("just now");
  });

  it("returns minutes ago", () => {
    const tenMinAgo = new Date(Date.now() - 10 * 60 * 1000).toISOString();
    expect(formatRelativeTime(tenMinAgo)).toBe("10 minutes ago");
  });

  it("returns singular minute", () => {
    const oneMinAgo = new Date(Date.now() - 61 * 1000).toISOString();
    expect(formatRelativeTime(oneMinAgo)).toBe("1 minute ago");
  });

  it("returns hours ago", () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeTime(twoHoursAgo)).toBe("2 hours ago");
  });

  it("returns days ago", () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeTime(threeDaysAgo)).toBe("3 days ago");
  });
});

describe("filterAndSort", () => {
  it("filters out conversations older than 30 days", () => {
    const recent = makeConv({ id: "1", updated_at: new Date().toISOString() });
    const old = makeConv({
      id: "2",
      updated_at: new Date(Date.now() - 31 * 24 * 60 * 60 * 1000).toISOString(),
    });
    expect(filterAndSort([recent, old])).toEqual([recent]);
  });

  it("sorts by most recent first", () => {
    const older = makeConv({
      id: "1",
      updated_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    });
    const newer = makeConv({
      id: "2",
      updated_at: new Date().toISOString(),
    });
    const result = filterAndSort([older, newer]);
    expect(result[0].id).toBe("2");
    expect(result[1].id).toBe("1");
  });

  it("returns empty array when all conversations are expired", () => {
    const old = makeConv({
      id: "1",
      updated_at: new Date(Date.now() - 31 * 24 * 60 * 60 * 1000).toISOString(),
    });
    expect(filterAndSort([old])).toEqual([]);
  });
});

describe("ConversationSidebar", () => {
  const defaultProps = {
    conversations: [] as ConversationSummary[],
    activeId: null,
    onSelect: jest.fn(),
    onDelete: jest.fn(),
    onNew: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the new conversation button", () => {
    render(<ConversationSidebar {...defaultProps} />);
    expect(screen.getByTestId("new-conversation-btn")).toBeInTheDocument();
  });

  it("calls onNew when new conversation button is clicked", () => {
    render(<ConversationSidebar {...defaultProps} />);
    fireEvent.click(screen.getByTestId("new-conversation-btn"));
    expect(defaultProps.onNew).toHaveBeenCalledTimes(1);
  });

  it("shows welcome prompt when no conversations exist", () => {
    render(<ConversationSidebar {...defaultProps} />);
    expect(screen.getByTestId("welcome-prompt")).toBeInTheDocument();
    expect(screen.getAllByTestId("suggested-starter")).toHaveLength(3);
  });

  it("shows conversation list when conversations exist", () => {
    const convs = [makeConv({ id: "c1" }), makeConv({ id: "c2" })];
    render(<ConversationSidebar {...defaultProps} conversations={convs} />);
    expect(screen.getByTestId("conversation-list")).toBeInTheDocument();
    expect(screen.getByTestId("conversation-c1")).toBeInTheDocument();
    expect(screen.getByTestId("conversation-c2")).toBeInTheDocument();
  });

  it("highlights the active conversation", () => {
    const convs = [makeConv({ id: "c1" }), makeConv({ id: "c2" })];
    render(<ConversationSidebar {...defaultProps} conversations={convs} activeId="c1" />);
    expect(screen.getByTestId("conversation-c1")).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("conversation-c2")).not.toHaveAttribute("aria-current");
  });

  it("calls onSelect when a conversation is clicked", () => {
    const convs = [makeConv({ id: "c1" })];
    render(<ConversationSidebar {...defaultProps} conversations={convs} />);
    fireEvent.click(screen.getByTestId("conversation-c1"));
    expect(defaultProps.onSelect).toHaveBeenCalledWith("c1");
  });

  it("calls onDelete when delete button is clicked", () => {
    const convs = [makeConv({ id: "c1" })];
    render(<ConversationSidebar {...defaultProps} conversations={convs} />);
    fireEvent.click(screen.getByTestId("delete-c1"));
    expect(defaultProps.onDelete).toHaveBeenCalledWith("c1");
    // Should not also trigger onSelect
    expect(defaultProps.onSelect).not.toHaveBeenCalled();
  });

  it("displays 'Untitled' for conversations with null title", () => {
    const convs = [makeConv({ id: "c1", title: null })];
    render(<ConversationSidebar {...defaultProps} conversations={convs} />);
    expect(screen.getByText("Untitled")).toBeInTheDocument();
  });

  it("filters out conversations older than 30 days", () => {
    const recent = makeConv({ id: "recent" });
    const old = makeConv({
      id: "old",
      updated_at: new Date(Date.now() - 31 * 24 * 60 * 60 * 1000).toISOString(),
    });
    render(<ConversationSidebar {...defaultProps} conversations={[recent, old]} />);
    expect(screen.getByTestId("conversation-recent")).toBeInTheDocument();
    expect(screen.queryByTestId("conversation-old")).not.toBeInTheDocument();
  });

  it("shows welcome prompt when all conversations are expired", () => {
    const old = makeConv({
      id: "old",
      updated_at: new Date(Date.now() - 31 * 24 * 60 * 60 * 1000).toISOString(),
    });
    render(<ConversationSidebar {...defaultProps} conversations={[old]} />);
    expect(screen.getByTestId("welcome-prompt")).toBeInTheDocument();
  });

  it("has accessible nav landmark", () => {
    render(<ConversationSidebar {...defaultProps} />);
    expect(screen.getByTestId("conversation-sidebar")).toHaveAttribute("aria-label", "Conversations");
  });
});
