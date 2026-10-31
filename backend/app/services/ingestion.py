import hashlib
import uuid
from pathlib import Path, PurePosixPath

from app.config import SAMPLES_DIR, settings
from app.db.seekdb import db
from app.services.chunking import parse_file


ALLOWED_SUFFIXES = {".md", ".txt", ".pdf"}


def _safe_relative_path(filename: str) -> str:
    normalized = filename.replace("\\", "/").lstrip("/")
    path = PurePosixPath(normalized)
    if not normalized or ".." in path.parts:
        raise ValueError("invalid file path")
    return str(path)


def import_files(user_id: str, files: list[tuple[str, bytes]]) -> list[dict]:
    outcomes = []
    for original_name, data in files:
        try:
            relative_path = _safe_relative_path(original_name)
            suffix = Path(relative_path).suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                outcomes.append({"file": relative_path, "status": "ignored"})
                continue
            if not data or len(data) > settings.max_file_bytes:
                raise ValueError("file is empty or exceeds 15 MiB")
            outcomes.append(_import_one(user_id, relative_path, data))
        except Exception as exc:
            outcomes.append(
                {"file": original_name, "status": "failed", "error": str(exc)}
            )
    return outcomes


def _import_one(user_id: str, relative_path: str, data: bytes) -> dict:
    content_hash = hashlib.sha256(data).hexdigest()
    existing = db.fetch_one(
        "SELECT * FROM documents WHERE user_id=%s AND relative_path=%s",
        (user_id, relative_path),
    )
    if existing and existing["content_hash"] == content_hash:
        return {
            "file": relative_path,
            "status": "skipped",
            "chunks": existing["chunk_count"],
        }

    chunks = parse_file(relative_path, data)
    if not chunks:
        raise ValueError("no extractable text")
    document_id = existing["document_id"] if existing else str(uuid.uuid4())
    if existing:
        with db._lock:
            db.collection.delete(
                where={
                    "$and": [
                        {"user_id": user_id},
                        {"document_id": document_id},
                    ]
                }
            )

    ids = []
    documents = []
    embeddings = []
    metadatas = []
    for chunk in chunks:
        chunk_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{user_id}:{relative_path}:{content_hash}:{chunk['chunk_index']}",
            )
        )
        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append(
            {
                "user_id": user_id,
                "document_id": document_id,
                "file_name": PurePosixPath(relative_path).name,
                "relative_path": relative_path,
                "file_type": PurePosixPath(relative_path).suffix[1:].lower(),
                "page_number": chunk["page_number"],
                "paragraph_start": chunk["paragraph_start"],
                "paragraph_end": chunk["paragraph_end"],
                "section_path": chunk["section_path"],
                "knowledge_point": chunk["knowledge_point"],
                "chunk_index": chunk["chunk_index"],
                "content_hash": content_hash,
            }
        )

    for start in range(0, len(documents), 16):
        batch = documents[start : start + 16]
        embeddings.extend(db.embedder(batch))

    with db._lock:
        for start in range(0, len(ids), 16):
            end = start + 16
            db.collection.upsert(
                ids=ids[start:end],
                documents=documents[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadatas[start:end],
            )
        db.execute(
            """
            INSERT INTO documents (
              document_id, user_id, file_name, relative_path, file_type,
              content_hash, chunk_count, import_status, error_message
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,'ready',NULL)
            ON DUPLICATE KEY UPDATE
              file_name=VALUES(file_name), file_type=VALUES(file_type),
              content_hash=VALUES(content_hash), chunk_count=VALUES(chunk_count),
              import_status='ready', error_message=NULL
            """,
            (
                document_id,
                user_id,
                PurePosixPath(relative_path).name,
                relative_path,
                PurePosixPath(relative_path).suffix[1:].lower(),
                content_hash,
                len(chunks),
            ),
        )
    return {
        "file": relative_path,
        "status": "imported",
        "chunks": len(chunks),
        "document_id": document_id,
    }


def import_samples(user_id: str) -> list[dict]:
    files = [
        (path.name, path.read_bytes())
        for path in sorted(SAMPLES_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES
    ]
    return import_files(user_id, files)
