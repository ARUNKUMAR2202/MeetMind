"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Link as LinkIcon, Mic, MicOff, PhoneOff, Users, Video, VideoOff } from "lucide-react";
import { useAuth } from "../../lib/auth-context";
import { useMeetingRoom } from "../../lib/useMeetingRoom";
import { VideoTile } from "../../components/VideoTile";
import { api, SessionOut } from "../../lib/api";

export default function RoomPage({ params }: { params: { sessionId: string } }) {
  const { token, user } = useAuth();
  const router = useRouter();
  const [session, setSession] = useState<SessionOut | null>(null);
  const [ending, setEnding] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  useEffect(() => {
    if (user) api.getSession(token, params.sessionId).then(setSession).catch(() => {});
  }, [user, token, params.sessionId]);

  const { localStream, participants, micOn, cameraOn, toggleMic, toggleCamera, state, error, endMeeting } =
    useMeetingRoom(params.sessionId, token, user?.id ?? "", user?.full_name ?? "Guest");

  async function handleEnd() {
    setEnding(true);
    const result = await endMeeting();
    if (result) {
      const destination = result.session_type === "student" ? "/student" : "/team";
      router.push(`${destination}/${result.id}`);
    } else {
      router.push("/sessions");
    }
  }

  async function copyInviteLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      /* clipboard permission denied — silently ignore, the URL is visible in the address bar anyway */
    }
  }

  if (error) {
    return (
      <div className="mx-auto max-w-md px-6 py-24 text-center">
        <p className="mb-4 font-body text-red-400">{error}</p>
        <button
          onClick={() => router.push("/sessions")}
          className="rounded-md border border-border px-4 py-2 font-body text-sm text-paper hover:border-muted"
        >
          Back to sessions
        </button>
      </div>
    );
  }

  const gridParticipants = [
    { peerId: "local", name: `${user?.full_name ?? "You"} (you)`, stream: localStream, isLocal: true },
    ...participants.map((p) => ({ ...p, name: p.name ?? "Joining…", isLocal: false })),
  ];

  return (
    <div className="mx-auto flex min-h-[calc(100vh-73px)] max-w-5xl flex-col px-4 py-6 sm:px-6 sm:py-8">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-xl font-medium text-paper">{session?.title ?? "Live meeting"}</h1>
          <p className="flex items-center gap-1.5 font-mono text-xs text-muted">
            {state === "connecting" && "Connecting…"}
            {state === "connected" && (
              <>
                <Users size={12} /> {gridParticipants.length} in the room · recording audio
              </>
            )}
            {state === "ending" && "Wrapping up and uploading…"}
          </p>
        </div>
        <button
          onClick={copyInviteLink}
          className="flex items-center gap-2 self-start rounded-md border border-border px-3 py-1.5 font-body text-xs text-paper transition hover:border-muted sm:self-auto"
        >
          {linkCopied ? <Check size={14} className="text-team" /> : <LinkIcon size={14} />}
          {linkCopied ? "Link copied" : "Copy invite link"}
        </button>
      </div>

      <div className="grid flex-1 grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {gridParticipants.map((p) => (
          <VideoTile key={p.peerId} stream={p.stream} label={p.name} muted={p.isLocal} mirrored={p.isLocal} />
        ))}
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
          onClick={handleEnd}
          disabled={ending}
          aria-label="End meeting and process"
          className="flex h-12 items-center gap-2 rounded-full bg-red-500 px-5 font-body text-sm font-medium text-white transition hover:bg-red-600 disabled:opacity-50"
        >
          <PhoneOff size={18} />
          {ending ? "Processing…" : "End & process"}
        </button>
      </div>
    </div>
  );
}
