"use client";

/**
 * Phase 1 has no login yet, so each browser gets a stable, client-generated id
 * (persisted in localStorage) that stands in for a user id — it's what host_id and
 * participants.user_id store on the backend. Phase 2 replaces this with the real
 * Supabase Auth user id once signup/login exist; nothing downstream needs to change
 * beyond swapping where this id comes from.
 */
const GUEST_ID_KEY = "meetmind_guest_id";
const GUEST_NAME_KEY = "meetmind_guest_name";

export function getGuestId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(GUEST_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(GUEST_ID_KEY, id);
  }
  return id;
}

export function getStoredDisplayName(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(GUEST_NAME_KEY) ?? "";
}

export function setStoredDisplayName(name: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(GUEST_NAME_KEY, name);
}
