"use client";

import { useState } from "react";
import Link from "next/link";
import { Video } from "lucide-react";
import { useAuth } from "./lib/auth-context";
import { UploadForm } from "./components/UploadForm";
import { LiveMeetingForm } from "./components/LiveMeetingForm";
import { WaveformMark } from "./components/WaveformMark";

export default function HomePage() {
  const { user, loading } = useAuth();
  const [mode, setMode] = useState<"upload" | "live">("upload");

  return (
    <div className="mx-auto max-w-5xl px-6 py-16">
      <section className="mb-14">
        <WaveformMark className="mb-8 h-16 w-full max-w-md" />
        <h1 className="mb-4 max-w-2xl font-display text-4xl font-medium leading-tight tracking-tight text-paper sm:text-5xl">
          Every session ends. What was said doesn&apos;t have to disappear.
        </h1>
        <p className="max-w-xl font-body text-lg leading-relaxed text-muted">
          MeetMind listens to your lecture or meeting and delivers a structured,
          role-specific record the moment it ends — summaries and quizzes for
          students, action items and role summaries for teams.
        </p>
      </section>

      <section className="mb-14 flex max-w-xl items-center justify-between gap-4 rounded-card border border-border bg-surface p-6">
        <div>
          <h2 className="mb-1 font-display text-lg font-medium text-paper">Start a live video meeting</h2>
          <p className="font-body text-sm text-muted">No account needed — create a room or join one with a code.</p>
        </div>
        <Link
          href="/meet"
          className="flex shrink-0 items-center gap-2 rounded-md bg-team px-4 py-2 font-body text-sm font-medium text-white hover:opacity-90"
        >
          <Video size={16} />
          Meet
        </Link>
      </section>

      {loading ? null : user ? (
        <section className="max-w-xl">
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
        </section>
      ) : (
        <section className="flex max-w-xl flex-col gap-3 rounded-card border border-border bg-surface p-6">
          <p className="font-body text-sm text-muted">Sign in to upload a recording and see it turned into structure.</p>
          <div className="flex gap-3">
            <Link href="/register" className="rounded-md bg-signal px-4 py-2 font-body text-sm font-medium text-ink hover:bg-signalDim">
              Create an account
            </Link>
            <Link href="/login" className="rounded-md border border-border px-4 py-2 font-body text-sm text-paper hover:border-muted">
              Log in
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}
