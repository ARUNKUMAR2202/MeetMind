"use client";

import { useEffect, useRef, useState } from "react";
import { api, SessionOut } from "./api";
import { useAuth } from "./auth-context";

export function useLiveSession(sessionId: string) {
  const { token, user } = useAuth();
  const [session, setSession] = useState<SessionOut | null>(null);
  const [stage, setStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    async function fetchSession() {
      try {
        const data = await api.getSession(token, sessionId);
        if (!cancelled) setSession(data);
        return data;
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load session.");
        return null;
      }
    }

    fetchSession().then((initial) => {
      if (!initial || initial.status === "completed" || initial.status === "failed") return;

      // Still processing — open a WebSocket for push updates. Stage-only messages
      // (e.g. {"status":"processing","stage":"transcribing"}) update the progress
      // label without a full re-fetch; a terminal status re-fetches for the results.
      const socket = new WebSocket(api.wsUrl(sessionId));
      socketRef.current = socket;
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.stage) setStage(message.stage);
          if (message.status === "completed" || message.status === "failed") {
            fetchSession();
          }
        } catch {
          fetchSession(); // malformed message — fall back to a full re-fetch
        }
      };
      socket.onerror = () => {
        // Fall back to polling if the socket can't connect (e.g. proxy/firewall issue).
        const interval = setInterval(async () => {
          const updated = await fetchSession();
          if (updated && (updated.status === "completed" || updated.status === "failed")) {
            clearInterval(interval);
          }
        }, 2500);
      };
    });

    return () => {
      cancelled = true;
      socketRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, token, sessionId]);

  return { session, stage, error };
}
