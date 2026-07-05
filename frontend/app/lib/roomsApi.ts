const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface RoomOut {
  id: string;
  code: string;
  host_id: string;
  status: "scheduled" | "live" | "ended";
  created_at: string;
  ended_at: string | null;
}

class RoomApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers as Record<string, string>) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* response wasn't JSON */
    }
    throw new RoomApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export const roomsApi = {
  create: (hostId: string, displayName: string) =>
    request<RoomOut>("/rooms", { method: "POST", body: JSON.stringify({ host_id: hostId, display_name: displayName }) }),

  getByCode: (code: string) => request<RoomOut>(`/rooms/by-code/${encodeURIComponent(code.trim().toUpperCase())}`),

  end: (roomId: string, userId: string) =>
    request<RoomOut>(`/rooms/${roomId}/end`, { method: "POST", body: JSON.stringify({ user_id: userId }) }),

  wsUrl: (roomId: string, userId: string, name: string) => {
    const wsBase = API_URL.replace(/^http/, "ws");
    const params = new URLSearchParams({ user_id: userId, name });
    return `${wsBase}/ws/rooms/${roomId}?${params.toString()}`;
  },
};

export { RoomApiError };
