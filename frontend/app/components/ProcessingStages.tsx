const STAGE_LABELS: Record<string, string> = {
  transcribing: "Transcribing audio",
  diarizing: "Identifying speakers",
  cleaning_transcript: "Cleaning up the transcript",
  summarizing: "Writing summaries",
  generating_quiz: "Generating quiz questions",
  extracting_action_items: "Extracting action items",
  finalizing: "Finalizing",
};

const STAGE_ORDER = [
  "transcribing", "diarizing", "cleaning_transcript",
  "summarizing", "generating_quiz", "extracting_action_items", "finalizing",
];

export function ProcessingStages({ currentStage }: { currentStage: string | null }) {
  const currentIndex = currentStage ? STAGE_ORDER.indexOf(currentStage) : -1;

  return (
    <div className="w-full max-w-xs">
      <p className="mb-3 text-center font-body text-sm text-muted">
        {currentStage ? STAGE_LABELS[currentStage] ?? currentStage : "Getting started…"}
      </p>
      <div className="flex gap-1">
        {STAGE_ORDER.map((stage, i) => (
          <div
            key={stage}
            className={`h-1 flex-1 rounded-full transition-colors ${
              currentIndex >= 0 && i <= currentIndex ? "bg-signal" : "bg-border"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
