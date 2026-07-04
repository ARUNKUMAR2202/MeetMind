import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./meetmind.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = int(os.getenv("JWT_EXPIRES_MINUTES", "1440"))

    # AWS S3 (Layer 7 storage, per thesis Chapter 4). If unset, audio is stored on
    # local disk under UPLOAD_DIR instead — fine for local dev, not for production.
    aws_s3_bucket: str = os.getenv("AWS_S3_BUCKET", "")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    upload_dir: str = os.getenv("UPLOAD_DIR", "./uploads")

    # Flip to "false" once you're testing against real audio + your own API keys.
    use_mock_pipeline: bool = os.getenv("USE_MOCK_PIPELINE", "true").lower() == "true"

    cors_origins: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

    # If set, session-status broadcasts and video-room signaling use Redis pub/sub
    # instead of in-process memory — required once you run more than one backend
    # instance (see services/pubsub.py, services/room_manager.py). Empty = in-memory
    # fallback, which is fine for a single dev/demo process.
    redis_url: str = os.getenv("REDIS_URL", "")

    # Rate limiting / upload guardrails
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "200"))

    # FERPA/GDPR: auto-delete stored audio this many days after a session completes.
    # 0 disables auto-deletion (keeps audio indefinitely).
    audio_retention_days: int = int(os.getenv("AUDIO_RETENTION_DAYS", "30"))

    # Auth cookie vs. bearer-token mode — see app/auth.py
    use_cookie_auth: bool = os.getenv("USE_COOKIE_AUTH", "true").lower() == "true"
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"


settings = Settings()
