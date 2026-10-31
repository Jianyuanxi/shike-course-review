import time
import uuid

from app.db.seekdb import db


WEAK_BOOST = 0.0005


def format_source(metadata: dict) -> str:
    location = (
        f"第 {metadata['page_number']} 页"
        if metadata.get("page_number") is not None
        else f"段落 {metadata['paragraph_start']}–{metadata['paragraph_end']}"
    )
    return f"{metadata['relative_path']} · {location}"


def search(user_id: str, query: str, weak_points: list[dict]) -> dict:
    started = time.perf_counter()
    search_id = str(uuid.uuid4())
    try:
        query_embedding = db.embedder.encode_query(query)
        with db._lock:
            raw = db.collection.hybrid_search(
                query={
                    "where_document": {"$contains": query},
                    "where": {"user_id": user_id},
                    "n_results": 20,
                },
                knn={
                    "query_embeddings": query_embedding,
                    "where": {"user_id": user_id},
                    "n_results": 20,
                },
                rank={"rrf": {}},
                n_results=20,
                include=["documents", "metadatas"],
            )
        ids = raw["ids"][0] if raw.get("ids") else []
        documents = raw["documents"][0] if raw.get("documents") else []
        metadatas = raw["metadatas"][0] if raw.get("metadatas") else []
        distances = raw["distances"][0] if raw.get("distances") else []
        weak_chunk_ids = {
            chunk_id
            for point in weak_points
            for chunk_id in point.get("chunk_ids", [])
        }
        candidates = []
        for index, (chunk_id, document, metadata) in enumerate(
            zip(ids, documents, metadatas), start=1
        ):
            rrf_score = 1 / (60 + index)
            weak_boost = WEAK_BOOST if chunk_id in weak_chunk_ids else 0
            candidates.append(
                {
                    "chunk_id": chunk_id,
                    "text": document,
                    "metadata": metadata,
                    "source": format_source(metadata),
                    "rrf_rank": index,
                    "rrf_score": rrf_score,
                    "weak_boost": weak_boost,
                    "final_score": rrf_score + weak_boost,
                    "distance": distances[index - 1]
                    if index <= len(distances)
                    else None,
                }
            )
        candidates.sort(key=lambda item: item["final_score"], reverse=True)
        for index, item in enumerate(candidates, start=1):
            item["final_rank"] = index
        results = candidates[:5]
        latency_ms = round((time.perf_counter() - started) * 1000)
        db.execute(
            """
            INSERT INTO search_logs (
              search_id, user_id, query_text, embedding_model, search_mode,
              result_count, status, latency_ms
            ) VALUES (%s,%s,%s,%s,'hybrid_fts_vector_rrf',%s,'success',%s)
            """,
            (
                search_id,
                user_id,
                query,
                db.embedder.model_name,
                len(results),
                latency_ms,
            ),
        )
        for item in candidates:
            db.execute(
                """
                INSERT INTO search_log_items (
                  search_id, chunk_id, rrf_rank, rrf_score, weak_boost,
                  final_score, final_rank, distance
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    search_id,
                    item["chunk_id"],
                    item["rrf_rank"],
                    item["rrf_score"],
                    item["weak_boost"],
                    item["final_score"],
                    item["final_rank"],
                    item["distance"],
                ),
            )
        return {
            "search_id": search_id,
            "results": results,
            "candidate_count": len(candidates),
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000)
        db.execute(
            """
            INSERT INTO search_logs (
              search_id, user_id, query_text, embedding_model, search_mode,
              result_count, status, error_message, latency_ms
            ) VALUES (%s,%s,%s,%s,'hybrid_fts_vector_rrf',0,'failed',%s,%s)
            """,
            (
                search_id,
                user_id,
                query,
                db.embedder.model_name,
                str(exc),
                latency_ms,
            ),
        )
        raise


def audit(user_id: str) -> dict:
    searches = db.fetch_all(
        "SELECT * FROM search_logs WHERE user_id=%s ORDER BY created_at DESC LIMIT 50",
        (user_id,),
    )
    items = db.fetch_all(
        """
        SELECT i.* FROM search_log_items i
        JOIN search_logs s ON s.search_id=i.search_id
        WHERE s.user_id=%s
        ORDER BY s.created_at DESC, i.final_rank
        LIMIT 200
        """,
        (user_id,),
    )
    memory = db.fetch_all(
        """
        SELECT operation_id, search_id, operation, http_method, endpoint,
               scope_id, artifact_ref, powercontext_request_id, status_code,
               success, response_summary, latency_ms, created_at
        FROM memory_operation_logs
        WHERE user_id=%s ORDER BY created_at DESC LIMIT 100
        """,
        (user_id,),
    )
    return {"searches": searches, "search_items": items, "memory_operations": memory}
