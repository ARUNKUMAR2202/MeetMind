"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Captions,
  Check,
  Circle,
  Link as LinkIcon,
  Mic,
  MicOff,
  MonitorUp,
  PhoneOff,
  Users,
  Video,
  VideoOff,
} from "lucide-react";
import { useAuth } from "../../lib/auth-context";
import { getGuestId, getStoredDisplayName, setStoredDisplayName } from "../../lib/guest";
import { roomsApi, RoomOut } from "../../lib/roomsApi";
import { useMeetRoom } from "../../lib/useMeetRoom";
import { VideoTile } from "../../components/VideoTile";
import { ParticipantList, ParticipantListEntry } from "../../components/ParticipantList";

type LoadState = "loading" | "not-found" | "ended" | "ready";

export default function MeetRoomPage({ params }: { params: { code: string } }) {
  const router = useRouter();
  const code = params.code.toUpperCase();
  const guestId = getGuestId();
  const { token, user } = useAuth();

  const [room, setRoom] = useState<RoomOut | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [joined, setJoined] = useState(false);
  const [displayName, setDisplayName] = useState(getStoredDisplayName());
  const [showParticipants, setShowParticipants] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [recordingNotice, setRecordingNotice] = useState(false);

  useEffect(() => {
    roomsApi
      .getByCode(code)
      .then((r) => {
        setRoom(r);
        setLoadState(r.status === "ended" ? "ended" : "ready");
      })
      .catch(() => setLoadState("not-found"));
  }, [code]);

  const isHost = room?.host_id === guestId;

  const {
    localStream,
    participants,
    micOn,
    cameraOn,
    screenSharing,
    toggleMic,
    toggleCamera,
    toggleScreenShare,
    state,
    error,
    leave,
    endForEveryone,
    recording,
    startRecording,
    stopRecording,
    captionsOn,
    toggleCaptions,
    captions,
  } = useMeetRoom(
    joined ? room?.id ?? "" : "",
    guestId,
    displayName || "Guest",
    token,
    `Meeting ${code}`,
    user?.account_type ?? "professional",
  );

  useEffect(() => {
    if (state === "left" || state === "ended") {
      const t = setTimeout(() => router.push("/meet"), state === "ended" ? 1500 : 0);
      return () => clearTimeout(t);
    }
  }, [state, router]);

  async function handleToggleRecording() {
    if (recording) {
      await stopRecording();
      setRecordingNotice(true);
      setTimeout(() => setRecordingNotice(false), 6000);
    } else {
      await startRecording();
    }
  }

  async function copyInviteLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      /* clipboard permission denied — the code is visible on screen anyway */
    }
  }

  if (loadState === "loading") {
    return <div className="mx-auto max-w-md px-6 py-24 text-center font-body text-muted">Looking up meeting…</div>;
  }
  if (loadState === "not-found") {
    return (
      <div className="mx-auto max-w-md px-6 py-24 text-center">
        <p className="mb-4 font-body text-red-400">No meeting found for code {code}.</p>
        <button onClick={() => router.push("/meet")} className="rounded-md border border-border px-4 py-2 font-body text-sm text-paper hover:border-muted">
          Back
        </button>
      </div>
    );
  }
  if (loadState === "ended" || state === "ended") {
    return <div className="mx-auto max-w-md px-6 py-24 text-center font-body text-muted">This meeting has ended.</div>;
  }
  if (state === "left") {
    return <div className="mx-auto max-w-md px-6 py-24 text-center font-body text-muted">You left the meeting.</div>;
  }

  if (!joined) {
    return (
      <div className="mx-auto max-w-md px-6 py-24">
        <h1 className="mb-1 font-display text-xl font-medium text-paper">Ready to join?</h1>
        <p className="mb-6 font-mono text-xs text-muted">Meeting code: {code}</p>
        <label className="mb-6 block">
          <span className="mb-1 block font-body text-xs text-muted">Your name</span>
          <input
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
              setStoredDisplayName(e.target.value);
            }}
            placeholder="e.g. Isabel"
            className="w-full rounded-md border border-border bg-surface px-3 py-2 font-body text-sm text-paper outline-none focus:border-muted"
          />
        </label>
        <button
          onClick={() => setJoined(true)}
          className="w-full rounded-md bg-team px-4 py-2 font-body text-sm font-medium text-white hover:opacity-90"
        >
          Join meeting
        </button>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-md px-6 py-24 text-center">
        <p className="mb-4 font-body text-red-400">{error}</p>
        <button onClick={() => router.push("/meet")} className="rounded-md border border-border px-4 py-2 font-body text-sm text-paper hover:border-muted">
          Back
        </button>
      </div>
    );
  }

  const gridParticipants = [
    { peerId: "local", name: `${displayName || "You"} (you)`, stream: localStream, isLocal: true },
    ...participants.map((p) => ({ ...p, name: p.name ?? "Joining…", isLocal: false })),
  ];

  const participantEntries: ParticipantListEntry[] = [
    { id: "local", name: displayName || "You", isLocal: true, isHost },
    ...participants.map((p) => ({ id: p.peerId, name: p.name ?? "Joining…", isLocal: false, isHost: false })),
  ];

  return (
    <div className="flex min-h-[calc(100vh-73px)]">
      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-4 py-6 sm:px-6 sm:py-8">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="font-display text-xl font-medium text-paper">Meeting {code}</h1>
            <p className="flex items-center gap-1.5 font-mono text-xs text-muted">
              {state === "connecting" && "Connecting…"}
              {state === "connected" && (
                <>
                  <Users size={12} /> {gridParticipants.length} in the room
                  {recording && (
                    <span className="ml-2 flex items-center gap-1 text-red-400">
                      <Circle size={8} className="fill-red-400" /> Recording
                    </span>
                  )}
                </>
              )}
            </p>
            {recordingNotice && (
              <p className="mt-1 font-body text-xs text-muted">
                Recording saved — the transcript will appear in{" "}
                <button onClick={() => router.push("/sessions")} className="underline hover:text-paper">
                  Sessions
                </button>{" "}
                once processing finishes.
              </p>
            )}
          </div>
          <button
            onClick={copyInviteLink}
            className="flex items-center gap-2 self-start rounded-md border border-border px-3 py-1.5 font-body text-xs text-paper transition hover:border-muted sm:self-auto"
          >
            {linkCopied ? <Check size={14} className="text-team" /> : <LinkIcon size={14} />}
            {linkCopied ? "Link copied" : "Copy invite link"}
          </button>
        </div>

        <div className="relative flex-1">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {gridParticipants.map((p) => (
              <VideoTile key={p.peerId} stream={p.stream} label={p.name} muted={p.isLocal} mirrored={p.isLocal} />
            ))}
          </div>
          {captionsOn && Object.keys(captions).length > 0 && (
            <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col items-center gap-1 pb-2">
              {Object.entries(captions).map(([peerId, c]) => (
                <span key={peerId} className="rounded bg-ink/80 px-3 py-1 font-body text-sm text-paper">
                  <span className="text-muted">{c.name}: </span>
                  {c.text}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="mt-8 flex items-center justify-center gap-4">
          <button
            onClick={toggleMic}
            aria-label={micOn ? "Mute microphone" : "Unmute microphone"}
            className={`flex h-12 w-12 items-center justify-center rounded-full border transition ${
              micOn ? "border-border text-paper hover:border-muted" : "border-red-500 bg-red-500/20 text-red-400"
            }`}
          >
            {micOn ? <Mic size={20} /> : <MicOff size={20} />}
          </button>
          <button
            onClick={toggleCamera}
            aria-label={cameraOn ? "Turn camera off" : "Turn camera on"}
            className={`flex h-12 w-12 items-center justify-center rounded-full border transition ${
              cameraOn ? "border-border text-paper hover:border-muted" : "border-red-500 bg-red-500/20 text-red-400"
            }`}
          >
            {cameraOn ? <Video size={20} /> : <VideoOff size={20} />}
          </button>
          <button
            onClick={toggleScreenShare}
            aria-label={screenSharing ? "Stop screen share" : "Share your screen"}
            className={`flex h-12 w-12 items-center justify-center rounded-full border transition ${
              screenSharing ? "border-signal bg-signal/20 text-signal" : "border-border text-paper hover:border-muted"
            }`}
          >
            <MonitorUp size={20} />
          </button>
          <button
            onClick={() => setShowParticipants((v) => !v)}
            aria-label="Toggle participant list"
            className={`flex h-12 w-12 items-center justify-center rounded-full border transition ${
              showParticipants ? "border-muted text-paper" : "border-border text-paper hover:border-muted"
            }`}
          >
            <Users size={20} />
          </button>
          <button
            onClick={toggleCaptions}
            aria-label={captionsOn ? "Turn off live captions" : "Turn on live captions"}
            className={`flex h-12 w-12 items-center justify-center rounded-full border transition ${
              captionsOn ? "border-signal bg-signal/20 text-signal" : "border-border text-paper hover:border-muted"
            }`}
          >
            <Captions size={20} />
          </button>
          {isHost && (
            <button
              onClick={handleToggleRecording}
              disabled={!user}
              title={user ? undefined : "Log in to record meetings"}
              aria-label={recording ? "Stop recording" : "Start recording"}
              className={`flex h-12 items-center gap-2 rounded-full border px-4 font-body text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                recording
                  ? "border-red-500 bg-red-500/20 text-red-400"
                  : "border-border text-paper hover:border-muted"
              }`}
            >
              <Circle size={14} className={recording ? "fill-red-400" : ""} />
              {recording ? "Stop recording" : "Record"}
            </button>
          )}
          <button
            onClick={leave}
            aria-label="Leave meeting"
            className="flex h-12 items-center gap-2 rounded-full border border-border px-5 font-body text-sm font-medium text-paper transition hover:border-muted"
          >
            <PhoneOff size={18} />
            Leave
          </button>
          {isHost && (
            <button
              onClick={endForEveryone}
              aria-label="End meeting for everyone"
              className="flex h-12 items-center gap-2 rounded-full bg-red-500 px-5 font-body text-sm font-medium text-white transition hover:bg-red-600"
            >
              End for everyone
            </button>
          )}
        </div>
      </div>

      {showParticipants && (
        <ParticipantList participants={participantEntries} onClose={() => setShowParticipants(false)} />
      )}
    </div>
  );
}
