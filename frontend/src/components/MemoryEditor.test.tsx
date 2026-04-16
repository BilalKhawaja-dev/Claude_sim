import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import MemoryEditor, { type UserMemoryEntry } from "./MemoryEditor";

function makeEntry(overrides: Partial<UserMemoryEntry> & { id: string }): UserMemoryEntry {
  const now = new Date().toISOString();
  return {
    content: "Test memory",
    created_at: now,
    updated_at: now,
    ...overrides,
  };
}

describe("MemoryEditor", () => {
  const defaultProps = {
    entries: [] as UserMemoryEntry[],
    onSave: jest.fn(),
    onDelete: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the component with heading", () => {
    render(<MemoryEditor {...defaultProps} />);
    expect(screen.getByText("User Memory")).toBeInTheDocument();
  });

  it("shows empty message when no entries exist", () => {
    render(<MemoryEditor {...defaultProps} />);
    expect(screen.getByTestId("empty-memory-msg")).toBeInTheDocument();
  });

  it("renders entries with edit and delete controls", () => {
    const entries = [makeEntry({ id: "m1", content: "I like TypeScript" })];
    render(<MemoryEditor {...defaultProps} entries={entries} />);
    expect(screen.getByTestId("memory-list")).toBeInTheDocument();
    expect(screen.getByTestId("memory-entry-m1")).toBeInTheDocument();
    expect(screen.getByText("I like TypeScript")).toBeInTheDocument();
    expect(screen.getByTestId("edit-btn-m1")).toBeInTheDocument();
    expect(screen.getByTestId("delete-btn-m1")).toBeInTheDocument();
  });

  it("renders multiple entries", () => {
    const entries = [
      makeEntry({ id: "m1", content: "Fact one" }),
      makeEntry({ id: "m2", content: "Fact two" }),
    ];
    render(<MemoryEditor {...defaultProps} entries={entries} />);
    expect(screen.getByText("Fact one")).toBeInTheDocument();
    expect(screen.getByText("Fact two")).toBeInTheDocument();
  });

  it("disables save button when textarea is empty", () => {
    render(<MemoryEditor {...defaultProps} />);
    const btn = screen.getByTestId("add-memory-btn");
    expect(btn).toBeDisabled();
  });

  it("enables save button when textarea has content", () => {
    render(<MemoryEditor {...defaultProps} />);
    fireEvent.change(screen.getByTestId("new-memory-input"), { target: { value: "New fact" } });
    expect(screen.getByTestId("add-memory-btn")).not.toBeDisabled();
  });

  it("calls onSave with new entry and clears textarea on add", () => {
    render(<MemoryEditor {...defaultProps} />);
    fireEvent.change(screen.getByTestId("new-memory-input"), { target: { value: "My preference" } });
    fireEvent.click(screen.getByTestId("add-memory-btn"));

    expect(defaultProps.onSave).toHaveBeenCalledTimes(1);
    const saved = defaultProps.onSave.mock.calls[0][0] as UserMemoryEntry;
    expect(saved.id).toBe("");
    expect(saved.content).toBe("My preference");
    // Textarea should be cleared
    expect(screen.getByTestId("new-memory-input")).toHaveValue("");
  });

  it("trims whitespace from new entry content", () => {
    render(<MemoryEditor {...defaultProps} />);
    fireEvent.change(screen.getByTestId("new-memory-input"), { target: { value: "  trimmed  " } });
    fireEvent.click(screen.getByTestId("add-memory-btn"));

    const saved = defaultProps.onSave.mock.calls[0][0] as UserMemoryEntry;
    expect(saved.content).toBe("trimmed");
  });

  it("does not call onSave when content is only whitespace", () => {
    render(<MemoryEditor {...defaultProps} />);
    fireEvent.change(screen.getByTestId("new-memory-input"), { target: { value: "   " } });
    expect(screen.getByTestId("add-memory-btn")).toBeDisabled();
  });

  it("calls onDelete with entry id", () => {
    const entries = [makeEntry({ id: "m1" })];
    render(<MemoryEditor {...defaultProps} entries={entries} />);
    fireEvent.click(screen.getByTestId("delete-btn-m1"));
    expect(defaultProps.onDelete).toHaveBeenCalledWith("m1");
  });

  it("enters edit mode when edit button is clicked", () => {
    const entries = [makeEntry({ id: "m1", content: "Original" })];
    render(<MemoryEditor {...defaultProps} entries={entries} />);
    fireEvent.click(screen.getByTestId("edit-btn-m1"));
    expect(screen.getByTestId("edit-memory-input-m1")).toHaveValue("Original");
    expect(screen.getByTestId("save-edit-m1")).toBeInTheDocument();
    expect(screen.getByTestId("cancel-edit-m1")).toBeInTheDocument();
  });

  it("calls onSave with updated content on edit save", () => {
    const entries = [makeEntry({ id: "m1", content: "Original" })];
    render(<MemoryEditor {...defaultProps} entries={entries} />);
    fireEvent.click(screen.getByTestId("edit-btn-m1"));
    fireEvent.change(screen.getByTestId("edit-memory-input-m1"), { target: { value: "Updated" } });
    fireEvent.click(screen.getByTestId("save-edit-m1"));

    expect(defaultProps.onSave).toHaveBeenCalledTimes(1);
    const saved = defaultProps.onSave.mock.calls[0][0] as UserMemoryEntry;
    expect(saved.id).toBe("m1");
    expect(saved.content).toBe("Updated");
  });

  it("exits edit mode on cancel", () => {
    const entries = [makeEntry({ id: "m1", content: "Original" })];
    render(<MemoryEditor {...defaultProps} entries={entries} />);
    fireEvent.click(screen.getByTestId("edit-btn-m1"));
    fireEvent.click(screen.getByTestId("cancel-edit-m1"));
    // Should be back to view mode
    expect(screen.queryByTestId("edit-memory-input-m1")).not.toBeInTheDocument();
    expect(screen.getByTestId("edit-btn-m1")).toBeInTheDocument();
  });

  it("has accessible labels", () => {
    const entries = [makeEntry({ id: "m1" })];
    render(<MemoryEditor {...defaultProps} entries={entries} />);
    expect(screen.getByLabelText("Add a new memory entry")).toBeInTheDocument();
    expect(screen.getByLabelText("Save new memory entry")).toBeInTheDocument();
    expect(screen.getByLabelText("Edit memory entry m1")).toBeInTheDocument();
    expect(screen.getByLabelText("Delete memory entry m1")).toBeInTheDocument();
  });

  it("has accessible list role on memory entries", () => {
    const entries = [makeEntry({ id: "m1" })];
    render(<MemoryEditor {...defaultProps} entries={entries} />);
    expect(screen.getByRole("list", { name: "Memory entries" })).toBeInTheDocument();
  });
});
