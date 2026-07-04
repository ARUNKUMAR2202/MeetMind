"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, SessionType } from "../lib/api";
import { useAuth } from "../lib/auth-context";

export function UploadForm() {
  const { token, user } = useAuth();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [sessionType, setSessionType] = useState<SessionType>(user?.account_type ?? "student");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!user || !file) return;
    setSubmitting(true);
    setError(null);
    try {
      const session = await api.createSession(token, title || file.name, sessionType, file);
      const destination = sessionType === "student" ? "/student" : "/team";
      router.push(`${destination}/${session.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Try again.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-card border border-border bg-surface p-6">
      <div className="mb-5">
        <label className="mb-2 block font-body text-sm text-muted">Session name</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Monday standup, Lecture 4 — Diarization"
          className="w-full rounded-md border border-border bg-ink px-3 py-2 font-body text-paper placeholder:text-muted/60"
        />
      </div>

      <div className="mb-5">
        <label className="mb-2 block font-body text-sm text-muted">Who is this for?</label>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => setSessionType("student")}
            className={`flex-1 rounded-md border px-4 py-2.5 text-left font-body text-sm transition ${
              sessionType === "student"
                ? "border-student bg-student/10 text-paper"
                : "border-border text-muted hover:border-muted"
            }`}
          >
            <div className="font-medium">Student</div>
            <div className="text-xs opacity-70">Summary, quiz, timestamps</div>
          </button>
          <button
            type="button"
            onClick={() => setSessionType("professional")}
            className={`flex-1 rounded-md border px-4 py-2.5 text-left font-body text-sm transition ${
              sessionType === "professional"
                ? "border-team bg-team/10 text-paper"
                : "border-border text-muted hover:border-muted"
            }`}
          >
            <div className="font-medium">Professional team</div>
            <div className="text-xs opacity-70">Action items, role summaries</div>
          </button>
        </div>
      </div>

      <div className="mb-6">
        <label className="mb-2 block font-body text-sm text-muted">Audio recording</label>
        <input
          type="file"
          accept="audio/*,video/*"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="w-full rounded-md border border-dashed border-border bg-ink px-3 py-4 font-body text-sm text-muted file:mr-4 file:rounded file:border-0 file:bg-signal file:px-3 file:py-1.5 file:text-ink file:font-medium"
        />
      </div>

      {error && <p className="mb-4 font-body text-sm text-red-400">{error}</p>}

      <button
        type="submit"
        disabled={!file || submitting}
        className="w-full rounded-md bg-signal py-2.5 font-body font-medium text-ink transition hover:bg-signalDim disabled:cursor-not-allowed disabled:opacity-40"
      >
        {submitting ? "Uploading…" : "Turn this into structured intelligence"}
      </button>
    </form>
  );
}
