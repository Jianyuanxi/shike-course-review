import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.db.seekdb import db


def concept_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())[:255]


class PowerContextService:
    def __init__(self) -> None:
        self._scope_lock = threading.RLock()

    def _request(
        self,
        user_id: str,
        operation: str,
        method: str,
        path: str,
        payload=None,
        scope_id: str | None = None,
        search_id: str | None = None,
        artifact_ref: str | None = None,
        headers: dict | None = None,
    ) -> tuple[dict, httpx.Headers]:
        request_headers = {"Content-Type": "application/json"}
        if settings.powercontext_token:
            request_headers["Authorization"] = (
                f"Bearer {settings.powercontext_token}"
            )
        if headers:
            request_headers.update(headers)
        started = time.perf_counter()
        status_code = None
        response_body = {}
        error = None
        try:
            with httpx.Client(timeout=30) as client:
                response = client.request(
                    method,
                    settings.powercontext_url + path,
                    json=payload,
                    headers=request_headers,
                )
            status_code = response.status_code
            response_body = response.json() if response.content else {}
            if response.is_error:
                error = str(response_body)
                raise RuntimeError(
                    f"PowerContext {operation} failed ({status_code}): {response_body}"
                )
            return response_body, response.headers
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000)
            request_id = None
            if "response" in locals():
                request_id = response.headers.get("x-powercontext-request-id")
            db.execute(
                """
                INSERT INTO memory_operation_logs (
                  operation_id, user_id, search_id, operation, http_method,
                  endpoint, scope_id, artifact_ref, powercontext_request_id,
                  status_code, success, request_summary, response_summary, latency_ms
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    search_id,
                    operation,
                    method,
                    path,
                    scope_id,
                    artifact_ref,
                    request_id,
                    status_code,
                    error is None,
                    json.dumps(payload, ensure_ascii=False)[:1500]
                    if payload is not None
                    else None,
                    (error or json.dumps(response_body, ensure_ascii=False))[:1500],
                    latency_ms,
                ),
            )

    def ensure_scope(self, user_id: str) -> str:
        with self._scope_lock:
            existing = db.fetch_one(
                "SELECT powercontext_scope_id FROM app_users WHERE user_id=%s",
                (user_id,),
            )
            if existing:
                return existing["powercontext_scope_id"]
            response, _ = self._request(
                user_id,
                "scope_create",
                "POST",
                "/v1/scopes",
                {
                    "title": f"Course review: {user_id}",
                    "summary": "Course queries and weak knowledge points",
                    "idempotency_key": f"course-review:{user_id}",
                },
            )
            scope_id = response["scope_id"]
            db.execute(
                "INSERT INTO app_users (user_id, powercontext_scope_id) VALUES (%s,%s)",
                (user_id, scope_id),
            )
            return scope_id

    def list_weak_points(self, user_id: str) -> list[dict]:
        scope_id = self.ensure_scope(user_id)
        response, _ = self._request(
            user_id,
            "memory_list_weak_points",
            "POST",
            "/v1/atomic-memory/list",
            {
                "scope_id": scope_id,
                "states": ["active"],
                "kind": "course_weak_point",
                "limit": 100,
            },
            scope_id=scope_id,
        )
        points = []
        for item in response.get("items", []):
            try:
                point = json.loads(item["text"])
            except (KeyError, json.JSONDecodeError):
                continue
            point["artifact_ref"] = (
                f"atomic-memory/{item['artifact']['artifact_id']}@"
                f"{item['artifact']['revision']}"
            )
            points.append(point)
        points.sort(
            key=lambda point: (
                point.get("query_count", 0),
                point.get("last_queried_at", ""),
            ),
            reverse=True,
        )
        return points

    def record_search(
        self,
        user_id: str,
        search_id: str,
        query: str,
        results: list[dict],
    ) -> None:
        scope_id = self.ensure_scope(user_id)
        evidence = {
            "search_id": search_id,
            "query": query,
            "results": [
                {"chunk_id": item["chunk_id"], "source": item["source"]}
                for item in results
            ],
        }
        self._request(
            user_id,
            "source_write_search",
            "POST",
            "/v1/sources/content",
            {
                "scope_id": scope_id,
                "source_id": f"course-search-{search_id}",
                "content": json.dumps(evidence, ensure_ascii=False),
                "metadata": {
                    "origin": "course-review-assistant",
                    "search_log_id": search_id,
                },
            },
            scope_id=scope_id,
            search_id=search_id,
        )

    def update_topic(
        self,
        user_id: str,
        search_id: str,
        query: str,
        results: list[dict],
    ) -> dict | None:
        if not results:
            return None
        top = results[0]
        concept = top["metadata"].get("knowledge_point") or query.strip()
        key = concept_key(concept)
        scope_id = self.ensure_scope(user_id)
        binding = db.fetch_one(
            "SELECT artifact_id FROM memory_bindings WHERE user_id=%s AND concept_key=%s",
            (user_id, key),
        )
        now = datetime.now(timezone.utc).isoformat()
        citations = [
            {
                "chunk_id": item["chunk_id"],
                "source": item["source"],
                "knowledge_point": item["metadata"].get("knowledge_point"),
            }
            for item in results
        ]
        if binding:
            artifact_id = binding["artifact_id"]
            path = (
                f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}"
            )
            current, headers = self._request(
                user_id,
                "memory_read_topic",
                "GET",
                path,
                scope_id=scope_id,
                search_id=search_id,
                artifact_ref=f"atomic-memory/{artifact_id}",
            )
            state = json.loads(current["content"]["text"])
            state["query_count"] = int(state.get("query_count", 0)) + 1
            state["last_queried_at"] = now
            state["recent_queries"] = (state.get("recent_queries", []) + [query])[-5:]
            state["chunk_ids"] = [item["chunk_id"] for item in results]
            state["sources"] = citations
            state["last_search_id"] = search_id
            kind = "course_weak_point" if state["query_count"] >= 2 else "course_topic"
            updated, _ = self._request(
                user_id,
                "memory_update_topic",
                "PUT",
                path,
                {
                    "content": {
                        "kind": kind,
                        "text": json.dumps(state, ensure_ascii=False),
                    }
                },
                scope_id=scope_id,
                search_id=search_id,
                artifact_ref=f"atomic-memory/{artifact_id}@{current['revision']}",
                headers={"If-Match": headers["etag"]},
            )
            state["artifact_ref"] = (
                f"atomic-memory/{artifact_id}@{updated['revision']}"
            )
            return state

        state = {
            "concept": concept,
            "concept_key": key,
            "query_count": 1,
            "first_queried_at": now,
            "last_queried_at": now,
            "recent_queries": [query],
            "chunk_ids": [item["chunk_id"] for item in results],
            "sources": citations,
            "last_search_id": search_id,
        }
        created, _ = self._request(
            user_id,
            "memory_create_topic",
            "POST",
            f"/v1/scopes/{scope_id}/artifacts",
            {
                "family": "atomic-memory",
                "content": {
                    "schema": "powercontext.atomic-memory.v1",
                    "kind": "course_topic",
                    "text": json.dumps(state, ensure_ascii=False),
                },
            },
            scope_id=scope_id,
            search_id=search_id,
        )
        artifact_id = created["artifact_id"]
        db.execute(
            """
            INSERT INTO memory_bindings (user_id, concept_key, artifact_id)
            VALUES (%s,%s,%s)
            ON DUPLICATE KEY UPDATE artifact_id=VALUES(artifact_id)
            """,
            (user_id, key, artifact_id),
        )
        state["artifact_ref"] = f"atomic-memory/{artifact_id}@1"
        return state

    def health(self) -> dict:
        with httpx.Client(timeout=5) as client:
            response = client.get(settings.powercontext_url + "/health/ready")
            response.raise_for_status()
            return response.json()


powercontext = PowerContextService()
