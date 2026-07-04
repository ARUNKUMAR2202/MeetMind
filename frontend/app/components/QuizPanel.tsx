"use client";

import { useState } from "react";
import { QuizQuestion } from "../lib/api";

const LEVEL_LABELS: Record<string, string> = {
  remembering: "Remembering",
  understanding: "Understanding",
  applying: "Applying",
};

function QuizItem({
  question, index, onSeek,
}: { question: QuizQuestion; index: number; onSeek?: (seconds: number) => void }) {
  const [selected, setSelected] = useState<number | null>(null);

  return (
    <div className="rounded-card border border-black/5 bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <span className="rounded-full bg-signal/15 px-2.5 py-1 font-body text-xs font-medium text-signalDim">
          {LEVEL_LABELS[question.bloom_level] ?? question.bloom_level}
        </span>
        <div className="flex items-center gap-2">
          {onSeek && (
            <button
              onClick={() => onSeek(question.source_segment_start)}
              className="font-mono text-xs text-student hover:underline"
            >
              ▶ jump to moment
            </button>
          )}
          <span className="font-mono text-xs text-mutedPaper">Q{index + 1}</span>
        </div>
      </div>
      <p className="mb-4 font-body text-sm font-medium text-ink">{question.question}</p>
      <div className="space-y-2">
        {question.options.map((option, i) => {
          const isSelected = selected === i;
          const isCorrect = i === question.correct_index;
          const showResult = selected !== null;
          return (
            <button
              key={i}
              onClick={() => setSelected(i)}
              disabled={selected !== null}
              className={`block w-full rounded-md border px-3 py-2 text-left font-body text-sm transition ${
                showResult && isCorrect
                  ? "border-team bg-team/10 text-ink"
                  : showResult && isSelected && !isCorrect
                  ? "border-red-400 bg-red-50 text-ink"
                  : "border-black/10 text-ink hover:border-student"
              }`}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function QuizPanel({
  quiz, flaggedCount, onSeek,
}: { quiz: QuizQuestion[]; flaggedCount: number; onSeek?: (seconds: number) => void }) {
  if (quiz.length === 0) {
    return <p className="font-body text-sm text-mutedPaper">No quiz questions yet.</p>;
  }

  return (
    <div>
      {flaggedCount > 0 && (
        <p className="mb-4 rounded-md bg-signal/10 px-3 py-2 font-body text-xs text-signalDim">
          {flaggedCount} question{flaggedCount === 1 ? "" : "s"} flagged for review — evidence
          couldn&apos;t be confidently matched back to the transcript.
        </p>
      )}
      <div className="space-y-4">
        {quiz.map((q, i) => (
          <QuizItem key={i} question={q} index={i} onSeek={onSeek} />
        ))}
      </div>
    </div>
  );
}
