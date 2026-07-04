"use client";

import { FormEvent, useState } from "react";
import { api, RetrievedDocument } from "../lib/api";
import { useAuth } from "../lib/auth-context";

export function DocumentPanel({
  sessionId,
  retrieved,
}: {
  sessionId: string;
  retrieved: RetrievedDocument[];
}) {
  const { token, user } = useAuth();
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    if (!user || !title.trim() || !text.trim()) return;
    setStatus("saving");
    try {
      await api.uploadDocument(token, sessionId, title, text);
      setStatus("saved");
      setTitle("");
      setText("");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="space-y-4">
      {retrieved.length > 0 ? (
        <div className="space-y-2">
          {retrieved.map((doc) => (
            <div key={doc.doc_id} className="rounded-card border border-black/5 bg-white p-4">
              <div className="mb-1 flex items-center justify-between">
                <span className="font-display text-sm font-medium text-ink">{doc.title}</span>
                <span className="font-mono text-xs text-mutedPaper">{Math.round(doc.score * 100)}% match</span>
              </div>
              <p className="font-body text-xs italic text-mutedPaper">
                Surfaced when someone said: &ldquo;{doc.triggered_by_quote}&rdquo;
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="font-body text-sm text-mutedPaper">
          No documents surfaced yet. Add a reference doc below — it&apos;ll be pulled up
          automatically whenever the transcript mentions something it covers.
        </p>
      )}

      <form onSubmit={handleAdd} className="rounded-card border border-dashed border-black/10 bg-white/60 p-4">
        <p className="mb-3 font-body text-xs text-mutedPaper">Add a reference document (paste text)</p>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Document title"
          className="mb-2 w-full rounded-md border border-black/10 bg-white px-3 py-2 font-body text-sm text-ink"
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste the document's text content…"
          rows={3}
          className="mb-3 w-full rounded-md border border-black/10 bg-white px-3 py-2 font-body text-sm text-ink"
        />
        <button
          type="submit"
          disabled={status === "saving"}
          className="rounded-md bg-team px-3 py-1.5 font-body text-sm font-medium text-white disabled:opacity-50"
        >
          {status === "saving" ? "Indexing…" : "Add document"}
        </button>
        {status === "saved" && <span className="ml-3 font-body text-xs text-team">Added.</span>}
        {status === "error" && <span className="ml-3 font-body text-xs text-red-500">Couldn&apos;t add that document.</span>}
      </form>
    </div>
  );
}
