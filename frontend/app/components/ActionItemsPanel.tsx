import { ActionItem } from "../lib/api";

export function ActionItemsPanel({
  items, bertscore, onSeek,
}: { items: ActionItem[]; bertscore: number | null; onSeek?: (seconds: number) => void }) {
  if (items.length === 0) {
    return <p className="font-body text-sm text-mutedPaper">No action items detected.</p>;
  }

  const byOwner = items.reduce<Record<string, ActionItem[]>>((acc, item) => {
    (acc[item.owner] ??= []).push(item);
    return acc;
  }, {});

  return (
    <div>
      {bertscore !== null && (
        <p className="mb-4 font-mono text-xs text-mutedPaper">
          Extraction quality (BERTScore proxy): {bertscore.toFixed(2)}{" "}
          <span className="text-muted">/ target 64.98 (Golia &amp; Kalita, 2023)</span>
        </p>
      )}
      <div className="space-y-4">
        {Object.entries(byOwner).map(([owner, tasks]) => (
          <div key={owner} className="rounded-card border border-black/5 bg-white p-5">
            <h3 className="mb-3 font-display text-sm font-medium text-ink">{owner}</h3>
            <ul className="space-y-2">
              {tasks.map((task, i) => (
                <li key={i} className="flex items-start justify-between gap-3 font-body text-sm">
                  <span className="text-ink">
                    {task.task}
                    {onSeek && (
                      <button
                        onClick={() => onSeek(task.source_segment_start)}
                        className="ml-2 font-mono text-xs text-student hover:underline"
                      >
                        ▶
                      </button>
                    )}
                  </span>
                  {task.due && (
                    <span className="shrink-0 rounded-full bg-team/10 px-2 py-0.5 font-mono text-xs text-team">
                      Due {task.due}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
