import pytest

from app.db.seekdb import db
from app.services.retrieval import WEAK_BOOST, format_source, search


class FakeEmbedder:
    model_name = "fake-local-model"

    def encode_query(self, query):
        return [0.1] * 512


class FakeCollection:
    def hybrid_search(self, **kwargs):
        metadata = [
            {
                "relative_path": f"{name}.pdf",
                "page_number": index,
                "paragraph_start": 0,
                "paragraph_end": 0,
                "knowledge_point": name,
            }
            for index, name in enumerate(("new", "other", "weak"), start=1)
        ]
        return {
            "ids": [["new", "other", "weak"]],
            "documents": [["new text", "other text", "weak text"]],
            "metadatas": [metadata],
            "distances": [[0.1, 0.2, 0.3]],
        }


def test_weak_boost_reorders_nearby_candidates_without_hiding_best_match(monkeypatch):
    statements = []
    monkeypatch.setattr(db, "embedder", FakeEmbedder())
    monkeypatch.setattr(db, "collection", FakeCollection())
    monkeypatch.setattr(db, "execute", lambda sql, params=None: statements.append((sql, params)))

    result = search("demo", "query", [{"chunk_ids": ["weak"]}])

    assert [item["chunk_id"] for item in result["results"]] == ["new", "weak", "other"]
    assert result["results"][0]["weak_boost"] == 0
    assert result["results"][1]["rrf_rank"] == 3
    assert result["results"][1]["final_rank"] == 2
    assert result["results"][1]["weak_boost"] == WEAK_BOOST
    assert result["results"][1]["final_score"] == pytest.approx(
        result["results"][1]["rrf_score"] + WEAK_BOOST
    )
    assert len(statements) == 4


def test_pdf_source_includes_page_number():
    source = format_source(
        {"relative_path": "slides.pdf", "page_number": 2, "paragraph_start": 0, "paragraph_end": 0}
    )

    assert source == "slides.pdf · 第 2 页"
