"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Video } from "lucide-react";
import { getGuestId, getStoredDisplayName, setStoredDisplayName } from "../lib/guest";
import { roomsApi, RoomApiError } from "../lib/roomsApi";

export default function MeetLandingPage() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState(getStoredDisplayName());
  const [joinCode, setJoinCode] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function saveName(name: string) {
    setDisplayName(name);
    setStoredDisplayName(name);
  }

  async function handleCreate() {
    setError(null);
    setCreating(true);
    try {
      const room = await roomsApi.create(getGuestId(), displayName || "Guest");
      router.push(`/meet/${room.code}`);
    } catch {
      setError("Couldn't create a meeting. Is the backend running?");
      setCreating(false);
    }
  }

  async function handleJoin() {
    if (!joinCode.trim()) return;
    setError(null);
    try {
      await roomsApi.getByCode(joinCode);
      router.push(`/meet/${joinCode.trim().toUpperCase()}`);
    } catch (err) {
      setError(err instanceof RoomApiError ? err.message : "Couldn't find that meeting.");
    }
  }

  return (
    <div className="mx-auto max-w-md px-6 py-16">
      <div className="mb-8 flex items-center gap-2">
        <Video size={22} className="text-team" />
        <h1 className="font-display text-2xl font-medium text-paper">Video meetings</h1>
      </div>

      <label className="mb-6 block">
        <span className="mb-1 block font-body text-xs text-muted">Your name</span>
        <input
          value={displayName}
          onChange={(e) => saveName(e.target.value)}
          placeholder="e.g. Isabel"
          className="w-full rounded-md border border-border bg-surface px-3 py-2 font-body text-sm text-paper outline-none focus:border-muted"
        />
      </label>

      <div className="mb-6 rounded-card border border-border bg-surface p-4">
        <p className="mb-3 font-body text-sm text-muted">Start a brand new meeting and share the code.</p>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="w-full rounded-md bg-team px-4 py-2 font-body text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {creating ? "Creating…" : "New meeting"}
        </button>
      </div>

      <div className="rounded-card border border-border bg-surface p-4">
        <p className="mb-3 font-body text-sm text-muted">Join a meeting with a code.</p>
        <div className="flex gap-2">
          <input
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleJoin()}
            placeholder="ABC123"
            className="flex-1 rounded-md border border-border bg-ink px-3 py-2 font-mono text-sm uppercase tracking-widest text-paper outline-none focus:border-muted"
          />
          <button
            onClick={handleJoin}
            className="rounded-md border border-border px-4 py-2 font-body text-sm text-paper transition hover:border-muted"
          >
            Join
          </button>
        </div>
      </div>

      {error && <p className="mt-4 font-body text-sm text-red-400">{error}</p>}
    </div>
  );
}
