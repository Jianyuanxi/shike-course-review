import pytest
from pydantic import ValidationError

from app.main import SearchRequest


def test_search_query_is_trimmed():
    assert SearchRequest(query="  混合检索  ").query == "混合检索"


def test_blank_search_query_is_rejected():
    with pytest.raises(ValidationError):
        SearchRequest(query="   ")
