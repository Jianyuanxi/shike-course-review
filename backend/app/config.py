import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SAMPLES_DIR = ROOT_DIR / "samples" / "course"


@dataclass(frozen=True)
class Settings:
    seekdb_host: str = os.getenv("SEEKDB_HOST", "127.0.0.1")
    seekdb_port: int = int(os.getenv("SEEKDB_PORT", "2881"))
    seekdb_database: str = os.getenv("SEEKDB_DATABASE", "course_review")
    seekdb_user: str = os.getenv("SEEKDB_USER", "root")
    seekdb_password: str = os.getenv("SEEKDB_PASSWORD", "")
    powercontext_url: str = os.getenv("POWERCONTEXT_URL", "http://127.0.0.1:8000").rstrip("/")
    powercontext_token: str = os.getenv("POWERCONTEXT_TOKEN", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "cpu")
    max_file_bytes: int = 15 * 1024 * 1024


settings = Settings()
