"""
Layer 6 — Document retrieval (Lewis et al., 2020, RAG + Jiang et al., 2024, RAG-Stack).

Two entry points:
- `index_document`: called when a user uploads a reference doc (slide deck, PDF, etc.)
  ahead of / during a session. Embeds and stores it in Pinecone.
- `retrieve_for_mention`: called continuously as the transcript streams in. Encodes a
  rolling window of the last `rag_context_window_minutes` of transcript (this is
  MeetMind's answer to the "no temporal relevance" limitation noted in the literature
  review — see thesis section 2.4) and returns documents whose similarity clears a
  confidence threshold, targeting Jiang et al.'s sub-2-second latency.
"""
from __future__ import annotations

import time
import uuid

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

from .config import settings
from .schemas import RetrievedDocument, Transcript

_CONFIDENCE_THRESHOLD = 0.75


def _openai_client() -> OpenAI:
    settings.require_openai()
    return OpenAI(api_key=settings.openai_api_key)


def _pinecone_index():
    settings.require_pinecone()
    pc = Pinecone(api_key=settings.pinecone_api_key)
    existing = {idx["name"] for idx in pc.list_indexes()}
    if settings.pinecone_index not in existing:
        # text-embedding-3-small = 1536 dimensions
        pc.create_index(
            name=settings.pinecone_index,
            dimension=1536,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return pc.Index(settings.pinecone_index)


def _embed(text: str) -> list[float]:
    resp = _openai_client().embeddings.create(model=settings.embedding_model, input=text)
    return resp.data[0].embedding


def index_document(session_id: str, title: str, text_chunks: list[str]) -> int:
    """Embeds and upserts each chunk of a document. Returns the number of chunks indexed."""
    index = _pinecone_index()
    vectors = []
    for chunk in text_chunks:
        vectors.append({
            "id": str(uuid.uuid4()),
            "values": _embed(chunk),
            "metadata": {"session_id": session_id, "title": title, "text": chunk[:1000]},
        })
    if vectors:
        index.upsert(vectors=vectors, namespace=session_id)
    return len(vectors)


def retrieve_for_mention(
    session_id: str,
    transcript: Transcript,
    at_timestamp: float,
    top_k: int = 3,
) -> tuple[list[RetrievedDocument], float]:
    """
    Returns (matches, latency_seconds). Builds the query from the rolling context
    window ending at `at_timestamp` rather than a single utterance, so a mention late
    in a meeting isn't matched against stale early-meeting context.
    """
    started = time.perf_counter()
    window_start = max(0.0, at_timestamp - settings.rag_context_window_minutes * 60)
    window_text = " ".join(
        s.text for s in transcript.segments if window_start <= s.end <= at_timestamp
    )
    if not window_text.strip():
        return [], time.perf_counter() - started

    index = _pinecone_index()
    query_vector = _embed(window_text)
    result = index.query(
        vector=query_vector, top_k=top_k, namespace=session_id, include_metadata=True,
    )

    matches = [
        RetrievedDocument(
            doc_id=m["id"],
            title=m["metadata"].get("title", "Untitled document"),
            score=m["score"],
            triggered_by_quote=window_text[-200:],
        )
        for m in result.get("matches", [])
        if m["score"] >= _CONFIDENCE_THRESHOLD
    ]
    return matches, time.perf_counter() - started
