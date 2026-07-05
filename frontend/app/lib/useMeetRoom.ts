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
 * Unlike useMeetingRoom.ts (the existing recording-linked hook), this one does not
 * record or upload audio anywhere — Phase 1 is the live call only. Recording lands
 * in Phase 3, at which point a room can be linked to a MeetingSession.
 */
import { useCallback, useEffect, useRef, useState } from "react";
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

interface SignalMessage {
  type: string;
  peer_id?: string;
  peers?: { peer_id: string; name: string | null }[];
  name?: string;
  from?: string;
  data?: { kind: string; sdp?: RTCSessionDescriptionInit; candidate?: RTCIceCandidateInit };
}

export function useMeetRoom(roomId: string, userId: string, displayName: string) {
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [participants, setParticipants] = useState<Record<string, RemoteParticipant>>({});
  const [micOn, setMicOn] = useState(true);
  const [cameraOn, setCameraOn] = useState(true);
  const [screenSharing, setScreenSharing] = useState(false);
  const [state, setState] = useState<MeetState>("connecting");
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const myPeerIdRef = useRef<string | null>(null);
  const peerConnectionsRef = useRef<Record<string, RTCPeerConnection>>({});
  const pendingCandidatesRef = useRef<Record<string, RTCIceCandidateInit[]>>({});
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const screenStreamRef = useRef<MediaStream | null>(null);

  const send = useCallback((message: object) => {
    socketRef.current?.readyState === WebSocket.OPEN && socketRef.current.send(JSON.stringify(message));
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
  }, [send]);

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

  const cleanup = useCallback(() => {
    socketRef.current?.close();
    Object.values(peerConnectionsRef.current).forEach((pc) => pc.close());
    peerConnectionsRef.current = {};
    cameraStreamRef.current?.getTracks().forEach((t) => t.stop());
    screenStreamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function join() {
      try {
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

  const leave = useCallback(() => {
    setState("leaving");
    cleanup();
    setState("left");
  }, [cleanup]);

  const endForEveryone = useCallback(() => {
    send({ type: "end-room" });
  }, [send]);

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
  };
}
