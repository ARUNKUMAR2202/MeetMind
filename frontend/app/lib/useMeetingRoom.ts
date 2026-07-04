"use client";

/**
 * Mesh WebRTC for small meetings (~2-6 people). Each participant connects directly
 * to every other participant — there's no media server. This keeps the stack simple
 * for a student/team meeting size, but it does NOT scale to a lecture hall; for large
 * classes, swap this for an SFU (LiveKit, mediasoup, etc.) behind the same hook
 * interface. No TURN server is configured, only public STUN — calls between peers on
 * restrictive/symmetric NATs (common on some corporate networks) may fail to connect;
 * add a TURN server here before relying on this across arbitrary networks.
 *
 * Only AUDIO is recorded (mixed down from every participant) and sent to the existing
 * pipeline — video is for the live call only, matching MeetMind's audio-based
 * architecture (see ai-pipeline/).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, SessionOut } from "./api";

const ICE_SERVERS: RTCConfiguration = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

interface RemoteParticipant {
  peerId: string;
  name: string | null;
  stream: MediaStream | null;
}

type ConnectionState = "connecting" | "connected" | "ending" | "ended" | "error";

interface SignalMessage {
  type: string;
  peer_id?: string;
  peers?: { peer_id: string; name: string | null }[];
  name?: string;
  from?: string;
  data?: { kind: string; sdp?: RTCSessionDescriptionInit; candidate?: RTCIceCandidateInit };
}

export function useMeetingRoom(sessionId: string, token: string | null, displayName: string) {
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [participants, setParticipants] = useState<Record<string, RemoteParticipant>>({});
  const [micOn, setMicOn] = useState(true);
  const [cameraOn, setCameraOn] = useState(true);
  const [state, setState] = useState<ConnectionState>("connecting");
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const myPeerIdRef = useRef<string | null>(null);
  const peerConnectionsRef = useRef<Record<string, RTCPeerConnection>>({});
  const pendingCandidatesRef = useRef<Record<string, RTCIceCandidateInit[]>>({});
  const localStreamRef = useRef<MediaStream | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const mixDestRef = useRef<MediaStreamAudioDestinationNode | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const send = useCallback((message: object) => {
    socketRef.current?.readyState === WebSocket.OPEN && socketRef.current.send(JSON.stringify(message));
  }, []);

  const addToMix = useCallback((stream: MediaStream) => {
    const ctx = audioContextRef.current;
    const dest = mixDestRef.current;
    if (!ctx || !dest) return;
    const audioTracks = stream.getAudioTracks();
    if (audioTracks.length === 0) return;
    const source = ctx.createMediaStreamSource(new MediaStream(audioTracks));
    source.connect(dest);
  }, []);

  const getOrCreatePeerConnection = useCallback((peerId: string): RTCPeerConnection => {
    let pc = peerConnectionsRef.current[peerId];
    if (pc) return pc;

    pc = new RTCPeerConnection(ICE_SERVERS);
    peerConnectionsRef.current[peerId] = pc;

    localStreamRef.current?.getTracks().forEach((track) => {
      pc!.addTrack(track, localStreamRef.current!);
    });

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        send({ type: "signal", to: peerId, data: { kind: "ice-candidate", candidate: event.candidate.toJSON() } });
      }
    };

    pc.ontrack = (event) => {
      const stream = event.streams[0];
      addToMix(stream);
      setParticipants((prev) => ({
        ...prev,
        [peerId]: { peerId, name: prev[peerId]?.name ?? null, stream },
      }));
    };

    pc.onconnectionstatechange = () => {
      if (pc!.connectionState === "failed" || pc!.connectionState === "closed") {
        delete peerConnectionsRef.current[peerId];
      }
    };

    return pc;
  }, [addToMix, send]);

  const flushPendingCandidates = useCallback(async (peerId: string, pc: RTCPeerConnection) => {
    const queued = pendingCandidatesRef.current[peerId] || [];
    pendingCandidatesRef.current[peerId] = [];
    for (const candidate of queued) {
      try {
        await pc.addIceCandidate(candidate);
      } catch {
        /* ignore stale candidates */
      }
    }
  }, []);

  const handleSignal = useCallback(async (from: string, data: NonNullable<SignalMessage["data"]>) => {
    if (data.kind === "offer" && data.sdp) {
      const pc = getOrCreatePeerConnection(from);
      await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
      await flushPendingCandidates(from, pc);
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      send({ type: "signal", to: from, data: { kind: "answer", sdp: answer } });
    } else if (data.kind === "answer" && data.sdp) {
      const pc = peerConnectionsRef.current[from];
      if (pc) {
        await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
        await flushPendingCandidates(from, pc);
      }
    } else if (data.kind === "ice-candidate" && data.candidate) {
      const pc = peerConnectionsRef.current[from];
      if (pc && pc.remoteDescription) {
        try {
          await pc.addIceCandidate(data.candidate);
        } catch {
          /* ignore */
        }
      } else {
        (pendingCandidatesRef.current[from] ??= []).push(data.candidate);
      }
    }
  }, [flushPendingCandidates, getOrCreatePeerConnection, send]);

  useEffect(() => {
    let cancelled = false;

    async function join() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        localStreamRef.current = stream;
        setLocalStream(stream);

        const AudioContextCtor = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = new AudioContextCtor();
        audioContextRef.current = ctx;
        mixDestRef.current = ctx.createMediaStreamDestination();
        addToMix(stream);

        const recorder = new MediaRecorder(mixDestRef.current.stream, { mimeType: "audio/webm" });
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunksRef.current.push(e.data);
        };
        recorder.start(1000);
        recorderRef.current = recorder;

        const socket = new WebSocket(api.roomWsUrl(sessionId));
        socketRef.current = socket;

        socket.onmessage = async (event) => {
          const message: SignalMessage = JSON.parse(event.data);

          switch (message.type) {
            case "welcome": {
              myPeerIdRef.current = message.peer_id!;
              if (displayName) send({ type: "hello", name: displayName });

              const existing = message.peers ?? [];
              setParticipants((prev) => {
                const next = { ...prev };
                for (const p of existing) next[p.peer_id] = { peerId: p.peer_id, name: p.name, stream: null };
                return next;
              });

              // We're the new joiner: offer to everyone already here.
              for (const p of existing) {
                const pc = getOrCreatePeerConnection(p.peer_id);
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                send({ type: "signal", to: p.peer_id, data: { kind: "offer", sdp: offer } });
              }
              setState("connected");
              break;
            }
            case "peer-joined":
              setParticipants((prev) => ({
                ...prev,
                [message.peer_id!]: { peerId: message.peer_id!, name: null, stream: null },
              }));
              break;
            case "peer-name":
              setParticipants((prev) => ({
                ...prev,
                [message.peer_id!]: { ...prev[message.peer_id!], peerId: message.peer_id!, name: message.name! },
              }));
              break;
            case "signal":
              if (message.from && message.data) await handleSignal(message.from, message.data);
              break;
            case "peer-left":
              peerConnectionsRef.current[message.peer_id!]?.close();
              delete peerConnectionsRef.current[message.peer_id!];
              setParticipants((prev) => {
                const next = { ...prev };
                delete next[message.peer_id!];
                return next;
              });
              break;
          }
        };

        socket.onerror = () => setError("Couldn't connect to the meeting room. Check your connection and try again.");
      } catch (err) {
        if (!cancelled) {
          setState("error");
          setError(
            err instanceof Error && err.name === "NotAllowedError"
              ? "Camera/microphone access was denied. Allow access and reload to join."
              : "Couldn't access your camera or microphone.",
          );
        }
      }
    }

    join();

    return () => {
      cancelled = true;
      socketRef.current?.close();
      Object.values(peerConnectionsRef.current).forEach((pc) => pc.close());
      localStreamRef.current?.getTracks().forEach((t) => t.stop());
      recorderRef.current?.state !== "inactive" && recorderRef.current?.stop();
      audioContextRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const toggleMic = useCallback(() => {
    const track = localStreamRef.current?.getAudioTracks()[0];
    if (track) {
      track.enabled = !track.enabled;
      setMicOn(track.enabled);
    }
  }, []);

  const toggleCamera = useCallback(() => {
    const track = localStreamRef.current?.getVideoTracks()[0];
    if (track) {
      track.enabled = !track.enabled;
      setCameraOn(track.enabled);
    }
  }, []);

  const endMeeting = useCallback(async (): Promise<SessionOut | null> => {
    setState("ending");
    const recorder = recorderRef.current;

    const recordingDone = new Promise<Blob>((resolve) => {
      if (!recorder || recorder.state === "inactive") {
        resolve(new Blob(chunksRef.current, { type: "audio/webm" }));
        return;
      }
      recorder.onstop = () => resolve(new Blob(chunksRef.current, { type: "audio/webm" }));
      recorder.stop();
    });

    const blob = await recordingDone;

    Object.values(peerConnectionsRef.current).forEach((pc) => pc.close());
    localStreamRef.current?.getTracks().forEach((t) => t.stop());
    socketRef.current?.close();
    audioContextRef.current?.close();
    setState("ended");

    if (blob.size === 0) return null;
    try {
      return await api.attachAudio(token, sessionId, blob, "meeting.webm");
    } catch {
      setError("The recording couldn't be uploaded. Please try again.");
      return null;
    }
  }, [sessionId, token]);

  return {
    localStream,
    participants: Object.values(participants),
    micOn,
    cameraOn,
    toggleMic,
    toggleCamera,
    state,
    error,
    endMeeting,
  };
}
