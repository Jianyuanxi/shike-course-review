import json

from app.services.powercontext import PowerContextService, concept_key


def test_concept_key_normalizes_whitespace_and_case():
    assert concept_key("  SeekDB\n  Hybrid  ") == "seekdb hybrid"


def test_weak_point_parsing_and_sorting(monkeypatch):
    service = PowerContextService()
    monkeypatch.setattr(service, "ensure_scope", lambda user_id: "scp_test")

    def request(*args, **kwargs):
        return {
            "items": [
                {
                    "text": json.dumps({"concept": "向量", "query_count": 2, "last_queried_at": "2026-01-01"}),
                    "artifact": {"artifact_id": "art_vector", "revision": 2},
                },
                {
                    "text": json.dumps({"concept": "混合检索", "query_count": 4, "last_queried_at": "2026-01-02"}),
                    "artifact": {"artifact_id": "art_hybrid", "revision": 4},
                },
            ]
        }, {}

    monkeypatch.setattr(service, "_request", request)

    points = service.list_weak_points("demo")

    assert [point["concept"] for point in points] == ["混合检索", "向量"]
    assert points[0]["artifact_ref"] == "atomic-memory/art_hybrid@4"
