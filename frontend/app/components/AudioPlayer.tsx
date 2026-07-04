"use client";

import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";

export interface AudioPlayerHandle {
  seekTo: (seconds: number) => void;
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export const AudioPlayer = forwardRef<AudioPlayerHandle, { src: string }>(function AudioPlayer(
  { src },
  ref,
) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState(false);

  useImperativeHandle(ref, () => ({
    seekTo: (seconds: number) => {
      if (!audioRef.current) return;
      audioRef.current.currentTime = seconds;
      audioRef.current.play().catch(() => {});
      setPlaying(true);
    },
  }));

  function togglePlay() {
    if (!audioRef.current) return;
    if (playing) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch(() => {});
    }
    setPlaying(!playing);
  }

  function handleSeekBarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const value = Number(e.target.value);
    if (audioRef.current) audioRef.current.currentTime = value;
    setCurrent(value);
  }

  if (error) {
    return (
      <p className="rounded-card border border-black/5 bg-white p-4 font-body text-xs text-mutedPaper">
        The original recording is no longer available for playback (it may have been
        auto-deleted per the data-retention policy — the transcript and results
        below are unaffected).
      </p>
    );
  }

  return (
    <div className="flex items-center gap-3 rounded-card border border-black/5 bg-white p-3">
      <audio
        ref={audioRef}
        src={src}
        onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
        onEnded={() => setPlaying(false)}
        onError={() => setError(true)}
        preload="metadata"
      />
      <button
        onClick={togglePlay}
        aria-label={playing ? "Pause" : "Play"}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-white"
      >
        {playing ? <Pause size={16} /> : <Play size={16} className="ml-0.5" />}
      </button>
      <span className="w-10 shrink-0 font-mono text-xs text-mutedPaper">{formatTime(current)}</span>
      <input
        type="range"
        min={0}
        max={duration || 0}
        value={current}
        onChange={handleSeekBarChange}
        className="h-1 flex-1 accent-student"
      />
      <span className="w-10 shrink-0 font-mono text-xs text-mutedPaper">{formatTime(duration)}</span>
    </div>
  );
});
