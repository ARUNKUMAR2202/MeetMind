"use client";

import { Crown, X } from "lucide-react";

export interface ParticipantListEntry {
  id: string;
  name: string;
  isLocal: boolean;
  isHost: boolean;
}

export function ParticipantList({
  participants,
  onClose,
}: {
  participants: ParticipantListEntry[];
  onClose: () => void;
}) {
  return (
    <div className="flex h-full w-full flex-col border-l border-border bg-surface sm:w-72">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="font-body text-sm font-medium text-paper">In this meeting ({participants.length})</h2>
        <button onClick={onClose} aria-label="Close participant list" className="text-muted hover:text-paper">
          <X size={16} />
        </button>
      </div>
      <ul className="flex-1 overflow-y-auto px-2 py-2">
        {participants.map((p) => (
          <li key={p.id} className="flex items-center gap-2 rounded-md px-2 py-2 font-body text-sm text-paper">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-border font-display text-xs text-muted">
              {p.name.slice(0, 1).toUpperCase()}
            </div>
            <span className="flex-1 truncate">
              {p.name}
              {p.isLocal && " (you)"}
            </span>
            {p.isHost && <Crown size={14} className="text-signal" aria-label="Host" />}
          </li>
        ))}
      </ul>
    </div>
  );
}
