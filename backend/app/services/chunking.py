import io
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class Paragraph:
    number: int
    text: str
    section: str
    page_number: int | None


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("gb18030")


def _text_paragraphs(text: str, title: str, markdown: bool) -> list[Paragraph]:
    paragraphs = []
    buffer = []
    section = title

    def flush() -> None:
        nonlocal buffer
        value = "\n".join(buffer).strip()
        buffer = []
        if value:
            paragraphs.append((value, section))

    for line in text.splitlines():
        heading = markdown and re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading:
            flush()
            section = heading.group(1).strip()
        elif not line.strip():
            flush()
        else:
            buffer.append(line.strip())
    flush()
    return [
        Paragraph(index, value, section_name, None)
        for index, (value, section_name) in enumerate(paragraphs)
    ]


def _split_long_paragraph(paragraph: Paragraph, max_chars: int) -> list[Paragraph]:
    text = paragraph.text
    if len(text) <= max_chars:
        return [paragraph]
    return [
        Paragraph(
            paragraph.number,
            text[start : start + max_chars].strip(),
            paragraph.section,
            paragraph.page_number,
        )
        for start in range(0, len(text), max_chars)
        if text[start : start + max_chars].strip()
    ]


def _pack_paragraphs(paragraphs: list[Paragraph]) -> list[dict]:
    expanded = []
    for paragraph in paragraphs:
        expanded.extend(_split_long_paragraph(paragraph, 900))

    chunks = []
    current = []
    current_length = 0

    def flush() -> None:
        nonlocal current, current_length
        if not current:
            return
        chunks.append(
            {
                "text": "\n\n".join(item.text for item in current),
                "paragraph_start": current[0].number,
                "paragraph_end": current[-1].number,
                "section_path": current[0].section,
                "knowledge_point": current[0].section,
                "page_number": current[0].page_number,
            }
        )
        current = []
        current_length = 0

    for paragraph in expanded:
        added_length = len(paragraph.text) + (2 if current else 0)
        if current and (
            current_length + added_length > 800
            or current[-1].section != paragraph.section
            or current[-1].page_number != paragraph.page_number
        ):
            flush()
        current.append(paragraph)
        current_length += added_length
    flush()
    return chunks


def parse_file(filename: str, data: bytes) -> list[dict]:
    suffix = Path(filename).suffix.lower()
    title = Path(filename).stem
    if suffix not in {".md", ".txt", ".pdf"}:
        raise ValueError("only md, txt and pdf are supported")

    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        chunks = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            paragraphs = [
                Paragraph(index, value, title, page_number)
                for index, value in enumerate(
                    part.strip()
                    for part in re.split(r"\n\s*\n", text)
                    if part.strip()
                )
            ]
            chunks.extend(_pack_paragraphs(paragraphs))
    else:
        text = _decode_text(data)
        paragraphs = _text_paragraphs(text, title, markdown=suffix == ".md")
        chunks = _pack_paragraphs(paragraphs)

    for index, chunk in enumerate(chunks):
        chunk["chunk_index"] = index
    return chunks
