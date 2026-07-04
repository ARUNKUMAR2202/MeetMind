import { ConceptSection } from "../lib/api";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function SummarySections({ sections }: { sections: ConceptSection[] }) {
  if (sections.length === 0) {
    return <p className="font-body text-sm text-mutedPaper">No sections yet.</p>;
  }

  return (
    <div className="space-y-4">
      {sections.map((section, i) => (
        <div key={i} className="rounded-card border border-black/5 bg-white p-5">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="font-display text-base font-medium text-ink">{section.title}</h3>
            <span className="font-mono text-xs text-student">
              {formatTime(section.start)}–{formatTime(section.end)}
            </span>
          </div>
          <p className="mb-3 font-body text-sm leading-relaxed text-mutedPaper">{section.summary}</p>
          <div className="flex flex-wrap gap-2">
            {section.key_concepts.map((concept, j) => (
              <span key={j} className="rounded-full bg-student/10 px-2.5 py-1 font-body text-xs text-student">
                {concept}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
