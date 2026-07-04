import { RoleSummary } from "../lib/api";

export function RoleSummaryPanel({ summaries }: { summaries: RoleSummary[] }) {
  if (summaries.length === 0) {
    return <p className="font-body text-sm text-mutedPaper">No role summaries yet.</p>;
  }

  return (
    <div className="space-y-3">
      {summaries.map((s, i) => (
        <div key={i} className="rounded-card border border-black/5 bg-white p-4">
          <div className="mb-1 font-display text-sm font-medium text-ink">{s.role}</div>
          <p className="font-body text-sm leading-relaxed text-mutedPaper">{s.summary}</p>
        </div>
      ))}
    </div>
  );
}
