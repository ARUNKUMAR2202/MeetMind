"use client";

/**
 * Mesh WebRTC for the Phase 1 live-room feature — every participant connects
 * directly to every other participant, no media server involved. Fine for small
 * meetings (~2-6 people); beyond ~6-8 the number of connections each browser has to
 * maintain (N-1 per participant) makes quality degrade, and you'd want an SFU
 * (LiveKit, mediasoup) mixing/forwarding streams server-side instead. No TURN
 * server is configured here either, only public STUN — calls between peers on
 * restrictive/symmetric NATs may fail to connect; add a TURN server before relying
 * on this across arbitrary networks.
 *
 * Phase 3: recording is host-only (a MeetingSession needs a real owner_id, and
 * guest rooms have no login) and mirrors the mixing approach in useMeetingRoom.ts —
 * the host's browser mixes every participant's audio via Web Audio API, records it,
 * and uploads it through the existing api.createLiveSession/attachAudio endpoints
 * once stopped. Live captions are separate and available to everyone: each
 * participant's own browser transcribes their own mic locally via the Web Speech
 * API and broadcasts the text over the room's signaling WebSocket — no backend ASR
 * service involved, so it only works in browsers that support
 * (webkit)SpeechRecognition (Chrome/Edge; not Firefox).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, SessionType } from "./api";
import { roomsApi } from "./roomsApi";

const ICE_SERVERS: RTCConfiguration = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

interface RemoteParticipant {
  peerId: string;
  name: string | null;
  stream: MediaStream | null;
}

export type MeetState = "connecting" | "connected" | "leaving" | "left" | "ended" | "error";

interface CaptionEntry {
  name: string;
  text: string;
}

interface SignalMessage {
  type: string;
  peer_id?: string;
  peers?: { peer_id: string; name: string | null }[];
  name?: string;
  from?: string;
  data?: { kind: string; sdp?: RTCSessionDescriptionInit; candidate?: RTCIceCandidateInit };
  text?: string;
  final?: boolean;
  recording?: boolean;
}

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}
interface SpeechRecognitionEventLike extends Event {
  results: { length: number; [index: number]: SpeechRecognitionResultLike };
}
interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function useMeetRoom(
  roomId: string,
  userId: string,
  displayName: string,
  token: string | null,
  sessionTitle: string,
  sessionType: SessionType,
) {
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [participants, setParticipants] = useState<Record<string, RemoteParticipant>>({});
  const [micOn, setMicOn] = useState(true);
  const [cameraOn, setCameraOn] = useState(true);
  const [screenSharing, setScreenSharing] = useState(false);
  const [state, setState] = useState<MeetState>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [captionsOn, setCaptionsOn] = useState(false);
  const [captions, setCaptions] = useState<Record<string, CaptionEntry>>({});

  const socketRef = useRef<WebSocket | null>(null);
  const myPeerIdRef = useRef<string | null>(null);
  const peerConnectionsRef = useRef<Record<string, RTCPeerConnection>>({});
  const pendingCandidatesRef = useRef<Record<string, RTCIceCandidateInit[]>>({});
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const screenStreamRef = useRef<MediaStream | null>(null);
  const participantsRef = useRef<Record<string, RemoteParticipant>>({});

  const audioContextRef = useRef<AudioContext | null>(null);
  const mixDestRef = useRef<MediaStreamAudioDestinationNode | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const sessionIdRef = useRef<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const captionTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    participantsRef.current = participants;
  }, [participants]);

  const send = useCallback((message: object) => {
    socketRef.current?.readyState === WebSocket.OPEN && socketRef.current.send(JSON.stringify(message));
  }, []);

  const showCaption = useCallback((key: string, name: string, text: string) => {
    setCaptions((prev) => ({ ...prev, [key]: { name, text } }));
    clearTimeout(captionTimersRef.current[key]);
    captionTimersRef.current[key] = setTimeout(() => {
      setCaptions((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }, 4000);
  }, []);

  const addToMix = useCallback((stream: MediaStream | null | undefined) => {
    const ctx = audioContextRef.current;
    const dest = mixDestRef.current;
    if (!ctx || !dest || !stream) return;
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

    cameraStreamRef.current?.getTracks().forEach((track) => {
      pc!.addTrack(track, cameraStreamRef.current!);
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

  const stopRecordingInternal = useCallback(async () => {
    const recorder = recorderRef.current;
    const currentSessionId = sessionIdRef.current;
    if (!recorder || !currentSessionId) return;

    const recordingDone = new Promise<Blob>((resolve) => {
      if (recorder.state === "inactive") {
        resolve(new Blob(chunksRef.current, { type: "audio/webm" }));
        return;
      }
      recorder.onstop = () => resolve(new Blob(chunksRef.current, { type: "audio/webm" }));
      recorder.stop();
    });

    const blob = await recordingDone;
    audioContextRef.current?.close();
    audioContextRef.current = null;
    mixDestRef.current = null;
    recorderRef.current = null;
    sessionIdRef.current = null;
    setRecording(false);

    if (blob.size > 0) {
      try {
        await api.attachAudio(token, currentSessionId, blob, "meeting.webm");
      } catch {
        /* upload failed — the session shell stays in "live" status, nothing more we can do here */
      }
    }
  }, [token]);

  const cleanup = useCallback(() => {
    socketRef.current?.close();
    Object.values(peerConnectionsRef.current).forEach((pc) => pc.close());
    peerConnectionsRef.current = {};
    cameraStreamRef.current?.getTracks().forEach((t) => t.stop());
    screenStreamRef.current?.getTracks().forEach((t) => t.stop());
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop();
    audioContextRef.current?.close();
    audioContextRef.current = null;
    mixDestRef.current = null;
    recorderRef.current = null;
  }, []);

  useEffect(() => {
    if (!roomId) return;
    let cancelled = false;

    async function join() {
      try {
        setError(null);
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        cameraStreamRef.current = stream;
        setLocalStream(stream);

        const socket = new WebSocket(roomsApi.wsUrl(roomId, userId, displayName));
        socketRef.current = socket;

        socket.onmessage = async (event) => {
          const message: SignalMessage = JSON.parse(event.data);

          switch (message.type) {
            case "welcome": {
              myPeerIdRef.current = message.peer_id!;
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
            case "caption":
              if (message.peer_id && message.text) {
                const name = participantsRef.current[message.peer_id]?.name ?? "Someone";
                showCaption(message.peer_id, name, message.text);
              }
              break;
            case "recording-state":
              setRecording(Boolean(message.recording));
              break;
            case "room-ended":
              cleanup();
              setState("ended");
              break;
          }
        };

        socket.onerror = () => setError("Couldn't connect to the meeting room. Check your connection and try again.");
        socket.onclose = (event) => {
          if (myPeerIdRef.current) return; // already joined — a real disconnect, not a rejection
          if (event.code === 4404) setError("This meeting no longer exists.");
          else if (event.code === 4410) setError("This meeting has ended.");
        };
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
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomId, userId]);

  const toggleMic = useCallback(() => {
    const track = cameraStreamRef.current?.getAudioTracks()[0];
    if (track) {
      track.enabled = !track.enabled;
      setMicOn(track.enabled);
    }
  }, []);

  const toggleCamera = useCallback(() => {
    const track = cameraStreamRef.current?.getVideoTracks()[0];
    if (track) {
      track.enabled = !track.enabled;
      setCameraOn(track.enabled);
    }
  }, []);

  const replaceOutgoingVideoTrack = useCallback((track: MediaStreamTrack) => {
    Object.values(peerConnectionsRef.current).forEach((pc) => {
      const sender = pc.getSenders().find((s) => s.track?.kind === "video");
      sender?.replaceTrack(track);
    });
  }, []);

  const toggleScreenShare = useCallback(async () => {
    if (screenSharing) {
      screenStreamRef.current?.getTracks().forEach((t) => t.stop());
      screenStreamRef.current = null;
      const cameraTrack = cameraStreamRef.current?.getVideoTracks()[0];
      if (cameraTrack) replaceOutgoingVideoTrack(cameraTrack);
      setLocalStream(cameraStreamRef.current);
      setScreenSharing(false);
      return;
    }

    try {
      const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
      screenStreamRef.current = screenStream;
      const screenTrack = screenStream.getVideoTracks()[0];
      replaceOutgoingVideoTrack(screenTrack);
      setLocalStream(screenStream);
      setScreenSharing(true);

      // Browser's own "Stop sharing" control ends the track without going through
      // toggleScreenShare() — listen for that so we can revert to the camera feed.
      screenTrack.onended = () => {
        screenStreamRef.current = null;
        const cameraTrack = cameraStreamRef.current?.getVideoTracks()[0];
        if (cameraTrack) replaceOutgoingVideoTrack(cameraTrack);
        setLocalStream(cameraStreamRef.current);
        setScreenSharing(false);
      };
    } catch {
      /* user cancelled the share picker — no state change needed */
    }
  }, [screenSharing, replaceOutgoingVideoTrack]);

  const startRecording = useCallback(async () => {
    if (recording) return;

    const AudioContextCtor =
      window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AudioContextCtor();
    audioContextRef.current = ctx;
    mixDestRef.current = ctx.createMediaStreamDestination();

    addToMix(cameraStreamRef.current);
    Object.values(participantsRef.current).forEach((p) => addToMix(p.stream));

    const recorder = new MediaRecorder(mixDestRef.current.stream, { mimeType: "audio/webm" });
    chunksRef.current = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.start(1000);
    recorderRef.current = recorder;

    try {
      const session = await api.createLiveSession(token, sessionTitle, sessionType);
      sessionIdRef.current = session.id;
      setRecording(true);
      send({ type: "recording-state", recording: true });
    } catch {
      recorder.stop();
      ctx.close();
      audioContextRef.current = null;
      mixDestRef.current = null;
      recorderRef.current = null;
    }
  }, [recording, token, addToMix, sessionTitle, sessionType, send]);

  const stopRecording = useCallback(async () => {
    await stopRecordingInternal();
    send({ type: "recording-state", recording: false });
  }, [stopRecordingInternal, send]);

  const toggleCaptions = useCallback(() => {
    setCaptionsOn((prev) => !prev);
  }, []);

  useEffect(() => {
    if (!captionsOn) return;
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;

    let stopped = false;

    function start() {
      const recognition = new Ctor!();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      recognition.onresult = (event) => {
        const result = event.results[event.results.length - 1];
        const text = result[0].transcript.trim();
        if (!text) return;
        showCaption("local", displayName || "You", text);
        send({ type: "caption", text, final: result.isFinal });
      };
      recognition.onend = () => {
        if (!stopped) start(); // browser stops recognition after a pause — restart while enabled
      };
      recognition.onerror = () => {
        /* transient (no-speech/network) — onend fires right after and restarts */
      };
      recognitionRef.current = recognition;
      recognition.start();
    }

    start();

    return () => {
      stopped = true;
      recognitionRef.current?.stop();
      recognitionRef.current = null;
    };
  }, [captionsOn, displayName, send, showCaption]);

  const leave = useCallback(async () => {
    setState("leaving");
    if (recording) await stopRecordingInternal();
    cleanup();
    setState("left");
  }, [cleanup, recording, stopRecordingInternal]);

  const endForEveryone = useCallback(async () => {
    if (recording) await stopRecordingInternal();
    send({ type: "end-room" });
  }, [recording, stopRecordingInternal, send]);

  return {
    myPeerId: myPeerIdRef.current,
    localStream,
    participants: Object.values(participants),
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
  };
}
