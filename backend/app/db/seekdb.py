import threading
from pathlib import Path

import pymysql
import pyseekdb
from pymysql.cursors import DictCursor
from pyseekdb import HNSWConfiguration

from app.config import settings
from app.services.embeddings import LocalEmbedder


class SeekDB:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.embedder = LocalEmbedder()
        self._connection = None
        self._client = None
        self.collection = None

    def initialize(self) -> None:
        with self._lock:
            if self.collection is not None:
                return
            common = {
                "host": settings.seekdb_host,
                "port": settings.seekdb_port,
                "user": settings.seekdb_user,
                "password": settings.seekdb_password,
            }
            admin = pyseekdb.AdminClient(**common)
            admin.create_database(settings.seekdb_database)
            self._client = pyseekdb.Client(
                **common,
                database=settings.seekdb_database,
            )
            if self._client.has_collection("course_chunks"):
                self.collection = self._client.get_collection(
                    "course_chunks",
                    embedding_function=self.embedder,
                )
            else:
                self.collection = self._client.create_collection(
                    name="course_chunks",
                    configuration=HNSWConfiguration(
                        dimension=self.embedder.dimension,
                        distance="cosine",
                    ),
                    embedding_function=self.embedder,
                )
            self._connection = pymysql.connect(
                **common,
                database=settings.seekdb_database,
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=True,
            )
            schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
            with self._connection.cursor() as cursor:
                for statement in schema.split(";"):
                    if statement.strip():
                        cursor.execute(statement)

    def execute(self, sql: str, params=None) -> None:
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(sql, params)

    def fetch_one(self, sql: str, params=None):
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()

    def fetch_all(self, sql: str, params=None) -> list[dict]:
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    def list_documents(self, user_id: str) -> list[dict]:
        return self.fetch_all(
            "SELECT * FROM documents WHERE user_id=%s ORDER BY imported_at DESC",
            (user_id,),
        )

    def get_chunks(self, chunk_ids: list[str], user_id: str) -> list[dict]:
        if not chunk_ids:
            return []
        with self._lock:
            result = self.collection.get(
                ids=chunk_ids,
                include=["documents", "metadatas"],
            )
        chunks = []
        for chunk_id, document, metadata in zip(
            result["ids"], result["documents"], result["metadatas"]
        ):
            if metadata.get("user_id") != user_id:
                continue
            chunks.append({"chunk_id": chunk_id, "text": document, "metadata": metadata})
        return chunks

    def get_context(self, chunk_id: str, user_id: str) -> dict:
        selected = self.get_chunks([chunk_id], user_id)
        if not selected:
            raise KeyError("chunk not found")
        target = selected[0]
        metadata = target["metadata"]
        index = int(metadata["chunk_index"])
        with self._lock:
            result = self.collection.get(
                where={
                    "$and": [
                        {"user_id": user_id},
                        {"document_id": metadata["document_id"]},
                        {"chunk_index": {"$gte": max(0, index - 2)}},
                        {"chunk_index": {"$lte": index + 2}},
                    ]
                },
                include=["documents", "metadatas"],
            )
        context = []
        for current_id, document, current_metadata in zip(
            result["ids"], result["documents"], result["metadatas"]
        ):
            context.append(
                {
                    "chunk_id": current_id,
                    "text": document,
                    "metadata": current_metadata,
                    "is_target": current_id == chunk_id,
                }
            )
        context.sort(key=lambda item: item["metadata"]["chunk_index"])
        return {"target": target, "context": context}


db = SeekDB()
