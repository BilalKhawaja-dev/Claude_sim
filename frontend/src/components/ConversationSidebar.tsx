/**
 * ConversationSidebar — lists conversations ordered by recency with
 * new/select/delete actions. Filters out conversations older than 30 days.
 * Shows a welcome prompt with suggested starters when no messages exist.
 *
 * Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6, 7.6
 */

import React from "react";

export interface ConversationSummary {
  id: string;
  title: string | null;
  updated_at: string; // ISO date string
}

export interface ConversationSidebarProps {
  conversations: ConversationSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
}

const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;

const SUGGESTED_STARTERS = [
  "Explain quantum computing in simple terms",
  "Help me write a Python script",
  "What are some creative project ideas?",
];

/** Return a human-friendly relative timestamp. */
export function formatRelativeTime(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

/** Filter and sort conversations: within 30 days, most recent first. */
export function filterAndSort(conversations: ConversationSummary[]): ConversationSummary[] {
  const cutoff = Date.now() - THIRTY_DAYS_MS;
  return conversations
    .filter((c) => new Date(c.updated_at).getTime() >= cutoff)
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
}

const styles = {
  sidebar: {
    width: 260,
    borderRight: "1px solid #e5e7eb",
    display: "flex",
    flexDirection: "column" as const,
    height: "100%",
    backgroundColor: "#f9fafb",
  },
  newButton: {
    margin: 12,
    padding: "10px 0",
    borderRadius: 8,
    border: "1px solid #d1d5db",
    backgroundColor: "#ffffff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  } as React.CSSProperties,
  list: {
    flex: 1,
    overflowY: "auto" as const,
    padding: "0 8px",
  },
  item: (active: boolean): React.CSSProperties => ({
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "10px 12px",
    borderRadius: 8,
    cursor: "pointer",
    backgroundColor: active ? "#e0e7ff" : "transparent",
    marginBottom: 2,
  }),
  title: {
    fontSize: 14,
    fontWeight: 500,
    overflow: "hidden" as const,
    textOverflow: "ellipsis" as const,
    whiteSpace: "nowrap" as const,
    flex: 1,
  } as React.CSSProperties,
  timestamp: {
    fontSize: 11,
    color: "#6b7280",
  } as React.CSSProperties,
  deleteBtn: {
    marginLeft: 8,
    padding: "2px 6px",
    border: "none",
    borderRadius: 4,
    backgroundColor: "transparent",
    color: "#ef4444",
    cursor: "pointer",
    fontSize: 12,
  } as React.CSSProperties,
  welcome: {
    padding: 24,
    textAlign: "center" as const,
    color: "#6b7280",
  },
  starterBtn: {
    display: "block",
    width: "100%",
    margin: "6px 0",
    padding: "8px 12px",
    borderRadius: 8,
    border: "1px solid #d1d5db",
    backgroundColor: "#ffffff",
    fontSize: 13,
    cursor: "pointer",
    textAlign: "left" as const,
  } as React.CSSProperties,
};

export default function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  onDelete,
  onNew,
}: ConversationSidebarProps) {
  const visible = filterAndSort(conversations);
  const showWelcome = visible.length === 0;

  return (
    <nav data-testid="conversation-sidebar" style={styles.sidebar} aria-label="Conversations">
      <button
        data-testid="new-conversation-btn"
        style={styles.newButton}
        onClick={onNew}
        aria-label="New conversation"
      >
        + New conversation
      </button>

      {showWelcome ? (
        <div data-testid="welcome-prompt" style={styles.welcome}>
          <p style={{ fontWeight: 600, marginBottom: 12 }}>Welcome! Start a conversation.</p>
          {SUGGESTED_STARTERS.map((starter) => (
            <button
              key={starter}
              data-testid="suggested-starter"
              style={styles.starterBtn}
              onClick={onNew}
            >
              {starter}
            </button>
          ))}
        </div>
      ) : (
        <div data-testid="conversation-list" style={styles.list} role="list">
          {visible.map((conv) => (
            <div
              key={conv.id}
              data-testid={`conversation-${conv.id}`}
              style={styles.item(conv.id === activeId)}
              role="listitem"
              onClick={() => onSelect(conv.id)}
              aria-current={conv.id === activeId ? "true" : undefined}
            >
              <div>
                <div style={styles.title}>{conv.title ?? "Untitled"}</div>
                <div style={styles.timestamp}>{formatRelativeTime(conv.updated_at)}</div>
              </div>
              <button
                data-testid={`delete-${conv.id}`}
                style={styles.deleteBtn}
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(conv.id);
                }}
                aria-label={`Delete conversation ${conv.title ?? conv.id}`}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </nav>
  );
}
