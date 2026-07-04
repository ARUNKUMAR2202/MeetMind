"""
Central settings for the AI pipeline. Everything reads from environment variables so
the same code runs locally, in CI, and in production without edits.

Copy backend/.env.example (repo root) to .env and fill in real keys before running
anything that touches OpenAI or Pinecone.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # --- LLM provider ---
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")
    whisper_model: str = os.getenv("WHISPER_MODEL", "whisper-1")

    # --- Vector DB (RAG, Lewis et al. 2020 / Jiang et al. 2024) ---
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY", "")
    pinecone_index: str = os.getenv("PINECONE_INDEX", "meetmind-documents")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # --- Optional heavy/real backends (see requirements-real-diarization.txt and
    # requirements-real-bertscore.txt — NOT installed by default). Both default to
    # off so the lightweight heuristic/proxy path (see diarization.py, action_items.py)
    # keeps mock mode and quick local dev fast and dependency-free. ---
    use_real_diarization: bool = os.getenv("USE_REAL_DIARIZATION", "false").lower() == "true"
    huggingface_token: str = os.getenv("HUGGINGFACE_TOKEN", "")
    use_real_bertscore: bool = os.getenv("USE_REAL_BERTSCORE", "false").lower() == "true"

    # --- Pipeline tuning ---
    # Golia & Kalita (2023) target for action-item summarization
    action_item_bertscore_target: float = 64.98
    # MeetMind's own evaluation target for quiz hallucination rate
    quiz_hallucination_target: float = 0.10
    # Jiang et al. (2024) — retrieval must surface documents under this many seconds
    retrieval_latency_target_seconds: float = 2.0
    # Tan et al. (2023) RPB preprocessing kicks in above this noise score (0-1, filler
    # word / disfluency ratio estimated over the raw transcript)
    noise_threshold: float = 0.15
    # Rolling context window (minutes) appended to RAG queries for temporal grounding
    rag_context_window_minutes: int = 2

    def require_openai(self) -> None:
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to your .env file — see "
                "backend/.env.example."
            )

    def require_pinecone(self) -> None:
        if not self.pinecone_api_key:
            raise RuntimeError(
                "PINECONE_API_KEY is not set. Add it to your .env file — see "
                "backend/.env.example."
            )


settings = Settings()
