"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../lib/auth-context";
import { SessionType } from "../lib/api";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accountType, setAccountType] = useState<SessionType>("student");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await register(email, password, fullName, accountType);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create your account.");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm px-6 py-20">
      <h1 className="mb-6 font-display text-2xl font-medium text-paper">Create an account</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          required
          placeholder="Full name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 font-body text-paper"
        />
        <input
          type="email"
          required
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 font-body text-paper"
        />
        <input
          type="password"
          required
          minLength={6}
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 font-body text-paper"
        />
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => setAccountType("student")}
            className={`flex-1 rounded-md border px-3 py-2 font-body text-sm ${
              accountType === "student" ? "border-student text-paper" : "border-border text-muted"
            }`}
          >
            I&apos;m a student
          </button>
          <button
            type="button"
            onClick={() => setAccountType("professional")}
            className={`flex-1 rounded-md border px-3 py-2 font-body text-sm ${
              accountType === "professional" ? "border-team text-paper" : "border-border text-muted"
            }`}
          >
            I&apos;m on a team
          </button>
        </div>
        {error && <p className="font-body text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-signal py-2 font-body font-medium text-ink hover:bg-signalDim disabled:opacity-50"
        >
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="mt-4 font-body text-sm text-muted">
        Already have an account?{" "}
        <Link href="/login" className="text-signal hover:underline">
          Log in
        </Link>
      </p>
    </div>
  );
}
