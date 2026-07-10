"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Video } from "lucide-react";
import { useAuth } from "../lib/auth-context";
import { api, SessionListItem } from "../lib/api";
import { UploadForm } from "../components/UploadForm";
import { LiveMeetingForm } from "../components/LiveMeetingForm";
import { StatusBadge } from "../components/StatusBadge";

export default function DashboardPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"upload" | "live">("upload");
  const [recent, setRecent] = useState<SessionListItem[] | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    api.listSessions(token).then(setRecent).catch(() => setRecent([]));
  }, [user, token]);

  if (loading || !user) {
    return <div className="mx-auto max-w-5xl px-6 py-16 font-body text-muted">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-16">
      <h1 className="mb-1 font-display text-2xl font-medium text-paper">Welcome back, {user.full_name}</h1>
      <p className="mb-10 font-body text-sm text-muted">Turn a recording into structure, or start a live session.</p>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section>
          <div className="mb-4 flex gap-1 rounded-md border border-border bg-surface p-1">
            <button
              onClick={() => setMode("upload")}
              className={`flex-1 rounded px-4 py-2 font-body text-sm transition ${
                mode === "upload" ? "bg-signal text-ink font-medium" : "text-muted hover:text-paper"
              }`}
            >
              Upload a recording
            </button>
            <button
              onClick={() => setMode("live")}
              className={`flex-1 rounded px-4 py-2 font-body text-sm transition ${
                mode === "live" ? "bg-team text-white font-medium" : "text-muted hover:text-paper"
              }`}
            >
              Start a live meeting
            </button>
          </div>
          {mode === "upload" ? <UploadForm /> : <LiveMeetingForm />}

          <div className="mt-6 flex items-center justify-between gap-4 rounded-card border border-border bg-surface p-5">
            <div>
              <h2 className="mb-1 font-display text-sm font-medium text-paper">Just want a video call?</h2>
              <p className="font-body text-xs text-muted">No recording or account needed — create a room or join one with a code.</p>
            </div>
            <Link
              href="/meet"
              className="flex shrink-0 items-center gap-2 rounded-md border border-border px-3 py-2 font-body text-sm text-paper hover:border-muted"
            >
              <Video size={16} />
              Meet
            </Link>
          </div>
        </section>

        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-sm font-medium text-paper">Recent sessions</h2>
            <Link href="/sessions" className="font-body text-xs text-signal hover:underline">
              View all
            </Link>
          </div>
          {recent === null ? (
            <p className="font-body text-sm text-muted">Loading…</p>
          ) : recent.length === 0 ? (
            <p className="font-body text-sm text-muted">No sessions yet — upload a recording to get started.</p>
          ) : (
            <div className="space-y-2">
              {recent.slice(0, 5).map((s) => (
                <Link
                  key={s.id}
                  href={`/${s.session_type === "student" ? "student" : "team"}/${s.id}`}
                  className="flex items-center justify-between rounded-card border border-border bg-surface px-4 py-3 transition hover:border-muted"
                >
                  <div className="min-w-0">
                    <div className="truncate font-display text-sm font-medium text-paper">{s.title}</div>
                    <div className="font-mono text-xs text-muted">{new Date(s.created_at).toLocaleDateString()}</div>
                  </div>
                  <StatusBadge status={s.status} />
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
