"""
Layer 3 — Preprocessing (Tan et al., 2023, "Reconstruct Before Summarize").

Only runs when Transcript.noise_score exceeds settings.noise_threshold (see
transcription.estimate_noise_score). Cleans filler words, merges repeated fragments,
and reorders broken utterances *without* changing meaning — this is a cleanup pass,
not a summarization pass, so downstream summarizers see cleaner input.
"""
from __future__ import annotations

from openai import OpenAI

from .config import settings
from .schemas import Transcript, TranscriptSegment

_RECONSTRUCTION_PROMPT = """You clean up noisy spoken-language transcripts. You will be \
given one utterance from a meeting or lecture. Rewrite it to remove filler words \
(um, uh, like, you know), merge stuttered repetitions, and fix fragmented word order — \
but do NOT summarize, do NOT remove any actual content or claims, and do NOT change who \
is speaking or what they committed to. If the utterance is already clean, return it \
unchanged. Return only the cleaned utterance, nothing else.

Utterance: {text}"""


def reconstruct_if_needed(transcript: Transcript) -> Transcript:
    if transcript.noise_score < settings.noise_threshold:
        return transcript

    settings.require_openai()
    client = OpenAI(api_key=settings.openai_api_key)
    cleaned_segments: list[TranscriptSegment] = []

    for seg in transcript.segments:
        if len(seg.text.split()) < 4:
            # Too short for the disfluency patterns RPB targets — skip to save cost/latency.
            cleaned_segments.append(seg)
            continue
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": _RECONSTRUCTION_PROMPT.format(text=seg.text)}],
            temperature=0,
        )
        cleaned_text = resp.choices[0].message.content.strip()
        cleaned_segments.append(seg.model_copy(update={"text": cleaned_text}))

    cleaned_raw_text = " ".join(s.text for s in cleaned_segments)
    return transcript.model_copy(update={
        "segments": cleaned_segments,
        "raw_text": cleaned_raw_text,
        "was_reconstructed": True,
    })
