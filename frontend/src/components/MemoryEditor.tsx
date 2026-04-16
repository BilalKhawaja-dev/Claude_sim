/**
 * MemoryEditor — displays user memory entries with edit/delete controls
 * and a text area for adding new entries.
 *
 * Validates: Requirements 5.1, 5.6
 */

import React, { useState } from "react";

export interface UserMemoryEntry {
  id: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryEditorProps {
  entries: UserMemoryEntry[];
  onSave: (entry: UserMemoryEntry) => void;
  onDelete: (id: string) => void;
}

const styles = {
  container: {
    maxWidth: 640,
    margin: "0 auto",
    padding: 24,
  },
  heading: {
    fontSize: 20,
    fontWeight: 600,
    marginBottom: 16,
  } as React.CSSProperties,
  newSection: {
    marginBottom: 24,
  },
  textarea: {
    width: "100%",
    minHeight: 80,
    padding: 10,
    borderRadius: 8,
    border: "1px solid #d1d5db",
    fontSize: 14,
    resize: "vertical" as const,
    boxSizing: "border-box" as const,
  },
  addBtn: {
    marginTop: 8,
    padding: "8px 16px",
    borderRadius: 8,
    border: "none",
    backgroundColor: "#4f46e5",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  } as React.CSSProperties,
  addBtnDisabled: {
    marginTop: 8,
    padding: "8px 16px",
    borderRadius: 8,
    border: "none",
    backgroundColor: "#a5b4fc",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "not-allowed",
  } as React.CSSProperties,
  entryCard: {
    padding: 12,
    marginBottom: 8,
    borderRadius: 8,
    border: "1px solid #e5e7eb",
    backgroundColor: "#f9fafb",
  },
  entryContent: {
    fontSize: 14,
    marginBottom: 8,
    whiteSpace: "pre-wrap" as const,
  },
  entryActions: {
    display: "flex",
    gap: 8,
  },
  editBtn: {
    padding: "4px 10px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    backgroundColor: "#fff",
    fontSize: 12,
    cursor: "pointer",
  } as React.CSSProperties,
  deleteBtn: {
    padding: "4px 10px",
    borderRadius: 6,
    border: "1px solid #fca5a5",
    backgroundColor: "#fff",
    color: "#ef4444",
    fontSize: 12,
    cursor: "pointer",
  } as React.CSSProperties,
  saveBtn: {
    padding: "4px 10px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "#4f46e5",
    color: "#fff",
    fontSize: 12,
    cursor: "pointer",
  } as React.CSSProperties,
  cancelBtn: {
    padding: "4px 10px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    backgroundColor: "#fff",
    fontSize: 12,
    cursor: "pointer",
  } as React.CSSProperties,
  editTextarea: {
    width: "100%",
    minHeight: 60,
    padding: 8,
    borderRadius: 6,
    border: "1px solid #d1d5db",
    fontSize: 14,
    resize: "vertical" as const,
    marginBottom: 8,
    boxSizing: "border-box" as const,
  },
  emptyMsg: {
    color: "#6b7280",
    fontSize: 14,
    textAlign: "center" as const,
    padding: 24,
  },
};

export default function MemoryEditor({ entries, onSave, onDelete }: MemoryEditorProps) {
  const [newContent, setNewContent] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const handleAdd = () => {
    const trimmed = newContent.trim();
    if (!trimmed) return;
    const now = new Date().toISOString();
    onSave({
      id: "",
      content: trimmed,
      created_at: now,
      updated_at: now,
    });
    setNewContent("");
  };

  const startEdit = (entry: UserMemoryEntry) => {
    setEditingId(entry.id);
    setEditContent(entry.content);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditContent("");
  };

  const handleEditSave = (entry: UserMemoryEntry) => {
    const trimmed = editContent.trim();
    if (!trimmed) return;
    onSave({ ...entry, content: trimmed, updated_at: new Date().toISOString() });
    setEditingId(null);
    setEditContent("");
  };

  return (
    <div data-testid="memory-editor" style={styles.container}>
      <h2 style={styles.heading}>User Memory</h2>

      <div style={styles.newSection}>
        <label htmlFor="new-memory-input" style={{ display: "block", marginBottom: 4, fontSize: 14, fontWeight: 500 }}>
          Add a new memory entry
        </label>
        <textarea
          id="new-memory-input"
          data-testid="new-memory-input"
          style={styles.textarea}
          placeholder="Enter a fact or preference…"
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
        />
        <button
          data-testid="add-memory-btn"
          style={newContent.trim() ? styles.addBtn : styles.addBtnDisabled}
          disabled={!newContent.trim()}
          onClick={handleAdd}
          aria-label="Save new memory entry"
        >
          Save
        </button>
      </div>

      {entries.length === 0 ? (
        <p data-testid="empty-memory-msg" style={styles.emptyMsg}>
          No memory entries yet. Add one above.
        </p>
      ) : (
        <div data-testid="memory-list" role="list" aria-label="Memory entries">
          {entries.map((entry) => (
            <div key={entry.id} data-testid={`memory-entry-${entry.id}`} role="listitem" style={styles.entryCard}>
              {editingId === entry.id ? (
                <>
                  <label htmlFor={`edit-memory-${entry.id}`} className="sr-only" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0,0,0,0)" }}>
                    Edit memory entry
                  </label>
                  <textarea
                    id={`edit-memory-${entry.id}`}
                    data-testid={`edit-memory-input-${entry.id}`}
                    style={styles.editTextarea}
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                  />
                  <div style={styles.entryActions}>
                    <button
                      data-testid={`save-edit-${entry.id}`}
                      style={styles.saveBtn}
                      onClick={() => handleEditSave(entry)}
                      aria-label="Save edited memory entry"
                    >
                      Save
                    </button>
                    <button
                      data-testid={`cancel-edit-${entry.id}`}
                      style={styles.cancelBtn}
                      onClick={cancelEdit}
                      aria-label="Cancel editing"
                    >
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div style={styles.entryContent}>{entry.content}</div>
                  <div style={styles.entryActions}>
                    <button
                      data-testid={`edit-btn-${entry.id}`}
                      style={styles.editBtn}
                      onClick={() => startEdit(entry)}
                      aria-label={`Edit memory entry ${entry.id}`}
                    >
                      Edit
                    </button>
                    <button
                      data-testid={`delete-btn-${entry.id}`}
                      style={styles.deleteBtn}
                      onClick={() => onDelete(entry.id)}
                      aria-label={`Delete memory entry ${entry.id}`}
                    >
                      Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
