"use client";

import { useEffect, useRef } from "react";

export function VideoTile({
  stream,
  label,
  muted = false,
  mirrored = false,
}: {
  stream: MediaStream | null;
  label: string;
  muted?: boolean;
  mirrored?: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = stream;
  }, [stream]);

  const hasVideo = !!stream?.getVideoTracks().some((t) => t.enabled);

  return (
    <div className="relative aspect-video overflow-hidden rounded-card bg-surfaceLight">
      {stream && hasVideo ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted={muted}
          className={`h-full w-full object-cover ${mirrored ? "-scale-x-100" : ""}`}
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-border font-display text-xl text-muted">
            {label.slice(0, 1).toUpperCase()}
          </div>
        </div>
      )}
      <span className="absolute bottom-2 left-2 rounded bg-ink/70 px-2 py-0.5 font-body text-xs text-paper">
        {label}
      </span>
    </div>
  );
}
