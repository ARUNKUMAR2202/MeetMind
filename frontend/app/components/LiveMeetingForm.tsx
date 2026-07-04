"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Video } from "lucide-react";
import { api, SessionType } from "../lib/api";
import { useAuth } from "../lib/auth-context";

export function LiveMeetingForm() {
  const { token, user } = useAuth();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [sessionType, setSessionType] = useState<SessionType>(user?.account_type ?? "student");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!user) return;
    setStarting(true);
    setError(null);
    try {
      const session = await api.createLiveSession(token, title || "Live meeting", sessionType);
      router.push(`/room/${session.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start the meeting.");
      setStarting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-card border border-border bg-surface p-6">
      <div className="mb-5">
        <label className="mb-2 block font-body text-sm text-muted">Meeting name</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Weekly sync, Office hours"
          className="w-full rounded-md border border-border bg-ink px-3 py-2 font-body text-paper placeholder:text-muted/60"
        />
      </div>

      <div className="mb-6">
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
            <div className="font-medium">Academic</div>
            <div className="text-xs opacity-70">Lecture or study group</div>
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
            <div className="font-medium">Professional</div>
            <div className="text-xs opacity-70">Team meeting</div>
          </button>
        </div>
      </div>

      {error && <p className="mb-4 font-body text-sm text-red-400">{error}</p>}

      <button
        type="submit"
        disabled={starting}
        className="flex w-full items-center justify-center gap-2 rounded-md bg-team py-2.5 font-body font-medium text-white transition hover:bg-team/90 disabled:opacity-50"
      >
        <Video size={18} />
        {starting ? "Starting…" : "Start live meeting now"}
      </button>
      <p className="mt-2 text-center font-body text-xs text-muted">
        Best for small groups (up to ~6 people). Camera/mic permission will be requested.
      </p>
    </form>
  );
}
