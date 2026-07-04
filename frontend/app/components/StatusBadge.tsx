import { SessionStatus } from "../lib/api";

const STYLES: Record<SessionStatus, string> = {
  live: "bg-red-500/20 text-red-400",
  uploaded: "bg-border text-muted",
  processing: "bg-signal/20 text-signal",
  completed: "bg-team/20 text-team",
  failed: "bg-red-500/20 text-red-400",
};

const LABELS: Record<SessionStatus, string> = {
  live: "Live",
  uploaded: "Uploaded",
  processing: "Processing…",
  completed: "Ready",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: SessionStatus }) {
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
