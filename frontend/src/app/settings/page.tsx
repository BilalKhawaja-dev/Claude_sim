/**
 * Settings page — wraps the MemoryEditor component.
 * Fetches user memory entries from the API and provides
 * save/delete handlers that call the backend.
 *
 * Validates: Requirements 5.1, 5.6
 */

"use client";

import React, { useEffect, useState, useCallback } from "react";
import MemoryEditor, { type UserMemoryEntry } from "@/components/MemoryEditor";
import { authHeaders } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function SettingsPage() {
  const [entries, setEntries] = useState<UserMemoryEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const fetchEntries = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/memory`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`Failed to load memory: ${res.status}`);
      const data: UserMemoryEntry[] = await res.json();
      setEntries(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load memory entries");
    }
  }, []);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const handleSave = async (entry: UserMemoryEntry) => {
    try {
      if (entry.id) {
        // Update existing
        const res = await fetch(`${API_BASE}/api/memory/${entry.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ content: entry.content }),
        });
        if (!res.ok) throw new Error(`Failed to update: ${res.status}`);
      } else {
        // Create new
        const res = await fetch(`${API_BASE}/api/memory`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ content: entry.content }),
        });
        if (!res.ok) throw new Error(`Failed to create: ${res.status}`);
      }
      await fetchEntries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save memory entry");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/memory/${id}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`Failed to delete: ${res.status}`);
      await fetchEntries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete memory entry");
    }
  };

  return (
    <main style={{ minHeight: "100vh", backgroundColor: "#fff" }}>
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "32px 16px" }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Settings</h1>
        {error && (
          <div data-testid="settings-error" role="alert" style={{ color: "#ef4444", marginBottom: 16, fontSize: 14 }}>
            {error}
          </div>
        )}
        <MemoryEditor entries={entries} onSave={handleSave} onDelete={handleDelete} />
      </div>
    </main>
  );
}
