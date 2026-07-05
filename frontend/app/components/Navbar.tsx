"use client";

import Link from "next/link";
import { useAuth } from "../lib/auth-context";

export function Navbar() {
  const { user, logout } = useAuth();

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/" className="font-display text-base font-medium tracking-tight text-paper sm:text-lg">
          MeetMind <span className="text-signal">AI</span>
        </Link>
        <nav className="flex items-center gap-2 font-body text-sm text-muted sm:gap-4">
          <Link href="/meet" className="hover:text-paper">
            Meet
          </Link>
          {user ? (
            <>
              <Link href="/sessions" className="hover:text-paper">
                Sessions
              </Link>
              <span className="hidden text-muted sm:inline">{user.full_name}</span>
              <button
                onClick={logout}
                className="rounded-md border border-border px-2.5 py-1.5 text-xs hover:border-muted hover:text-paper sm:px-3 sm:text-sm"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="hover:text-paper">
                Log in
              </Link>
              <Link
                href="/register"
                className="rounded-md bg-signal px-2.5 py-1.5 text-xs font-medium text-ink hover:bg-signalDim sm:px-3 sm:text-sm"
              >
                Get started
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
