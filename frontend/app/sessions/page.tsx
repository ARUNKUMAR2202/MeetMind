"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { useAuth } from "../lib/auth-context";
import { api, SessionListItem } from "../lib/api";
import { StatusBadge } from "../components/StatusBadge";

export default function SessionsPage() {
  const { token, user, loading: authLoading } = useAuth();
  const [sessions, setSessions] = useState<SessionListItem[] | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api.listSessions(token).then(setSessions).catch(() => setSessions([]));
  }, [user, token]);

  async function handleDelete(id: string) {
    if (!user) return;
    setDeletingId(id);
    try {
      await api.deleteSession(token, id);
      setSessions((prev) => prev?.filter((s) => s.id !== id) ?? null);
    } finally {
      setDeletingId(null);
      setConfirmingId(null);
    }
  }

  if (authLoading || sessions === null) {
    return <div className="mx-auto max-w-3xl px-6 py-16 font-body text-muted">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="mb-8 font-display text-2xl font-medium text-paper">My sessions</h1>
      {sessions.length === 0 ? (
        <p className="font-body text-muted">
          No sessions yet.{" "}
          <Link href="/" className="text-signal hover:underline">
            Upload your first recording
          </Link>
          .
        </p>
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between rounded-card border border-border bg-surface px-5 py-4 transition hover:border-muted"
            >
              <Link href={`/${s.session_type === "student" ? "student" : "team"}/${s.id}`} className="flex-1">
                <div className="font-display text-sm font-medium text-paper">{s.title}</div>
                <div className="font-mono text-xs text-muted">
                  {new Date(s.created_at).toLocaleString()} · {s.session_type}
                </div>
              </Link>
              <div className="flex items-center gap-3">
                <StatusBadge status={s.status} />
                {confirmingId === s.id ? (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleDelete(s.id)}
                      disabled={deletingId === s.id}
                      className="rounded-md bg-red-500 px-2.5 py-1 font-body text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
                    >
                      {deletingId === s.id ? "Deleting…" : "Confirm"}
                    </button>
                    <button
                      onClick={() => setConfirmingId(null)}
                      className="font-body text-xs text-muted hover:text-paper"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmingId(s.id)}
                    aria-label={`Delete ${s.title}`}
                    className="rounded-md p-1.5 text-muted transition hover:bg-red-500/10 hover:text-red-400"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
