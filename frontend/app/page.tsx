"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "./lib/auth-context";
import { WaveformMark } from "./components/WaveformMark";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  if (loading || user) return null;

  return (
    <div className="mx-auto max-w-5xl px-6 py-16">
      <section className="mb-14">
        <WaveformMark className="mb-8 h-16 w-full max-w-md" />
        <h1 className="mb-4 max-w-2xl font-display text-4xl font-medium leading-tight tracking-tight text-paper sm:text-5xl">
          Every session ends. What was said doesn&apos;t have to disappear.
        </h1>
        <p className="max-w-xl font-body text-lg leading-relaxed text-muted">
          MeetMind listens to your lecture or meeting and delivers a structured,
          role-specific record the moment it ends — summaries and quizzes for
          students, action items and role summaries for teams.
        </p>
      </section>

      <section className="flex max-w-xl flex-col gap-3 rounded-card border border-border bg-surface p-6">
        <p className="font-body text-sm text-muted">Sign in to upload a recording and see it turned into structure.</p>
        <div className="flex gap-3">
          <Link href="/register" className="rounded-md bg-signal px-4 py-2 font-body text-sm font-medium text-ink hover:bg-signalDim">
            Create an account
          </Link>
          <Link href="/login" className="rounded-md border border-border px-4 py-2 font-body text-sm text-paper hover:border-muted">
            Log in
          </Link>
        </div>
      </section>
    </div>
  );
}
