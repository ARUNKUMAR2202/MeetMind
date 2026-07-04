"use client";

import { TranscriptSegment } from "../lib/api";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

const SPEAKER_COLORS = ["text-student", "text-team", "text-signalDim"];

function speakerColor(speaker: string | null | undefined, knownSpeakers: string[]): string {
  if (!speaker) return "text-mutedPaper";
  const idx = knownSpeakers.indexOf(speaker) % SPEAKER_COLORS.length;
  return SPEAKER_COLORS[idx];
}

export function TranscriptView({
  segments,
  onSeek,
}: {
  segments: TranscriptSegment[];
  onSeek?: (seconds: number) => void;
}) {
  if (segments.length === 0) {
    return <p className="font-body text-sm text-mutedPaper">No transcript available.</p>;
  }

  const knownSpeakers = Array.from(new Set(segments.map((s) => s.speaker).filter(Boolean))) as string[];

  return (
    <div className="max-h-96 space-y-3 overflow-y-auto rounded-card border border-black/5 bg-white p-4">
      {segments.map((seg, i) => (
        <button
          key={i}
          onClick={() => onSeek?.(seg.start)}
          disabled={!onSeek}
          className="block w-full text-left"
        >
          <div className="flex items-baseline gap-2">
            <span className={`shrink-0 font-body text-xs font-medium ${speakerColor(seg.speaker, knownSpeakers)}`}>
              {seg.speaker ?? "Unknown"}
            </span>
            <span className="shrink-0 font-mono text-xs text-mutedPaper/70">{formatTime(seg.start)}</span>
          </div>
          <p className="font-body text-sm leading-relaxed text-ink hover:text-student">{seg.text}</p>
        </button>
      ))}
    </div>
  );
}
