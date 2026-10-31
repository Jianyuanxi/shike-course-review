from app.config import SAMPLES_DIR
from app.services.chunking import parse_file
from app.services.ingestion import _safe_relative_path


def test_markdown_preserves_sections_and_paragraphs():
    data = "# 混合检索\n\n第一段介绍关键词。\n\n第二段介绍向量。\n\n# 复习清单\n\n核对出处。".encode()

    chunks = parse_file("notes.md", data)

    assert [chunk["section_path"] for chunk in chunks] == ["混合检索", "复习清单"]
    assert chunks[0]["paragraph_start"] == 0
    assert chunks[0]["paragraph_end"] == 1
    assert chunks[0]["knowledge_point"] == "混合检索"


def test_gb18030_txt_is_supported():
    chunks = parse_file("notes.txt", "本地向量\n\n不需要密钥。".encode("gb18030"))

    assert len(chunks) == 1
    assert "不需要密钥" in chunks[0]["text"]


def test_pdf_pages_are_not_merged():
    path = SAMPLES_DIR / "04-检索评估速查.pdf"

    chunks = parse_file(path.name, path.read_bytes())

    assert len(chunks) == 2
    assert [chunk["page_number"] for chunk in chunks] == [1, 2]
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1]
    assert "PDF 页码验收" in chunks[1]["text"]


def test_upload_path_cannot_escape():
    assert _safe_relative_path("folder\\notes.md") == "folder/notes.md"

    try:
        _safe_relative_path("../secret.md")
    except ValueError as exc:
        assert str(exc) == "invalid file path"
    else:
        raise AssertionError("path traversal must be rejected")
