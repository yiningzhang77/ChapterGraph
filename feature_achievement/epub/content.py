from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

_TAG_BLOCK_BREAK_RE = re.compile(
    r"</?(?:p|div|h1|h2|h3|h4|h5|h6|li|ul|ol|tr|table|section|article|br)\b[^>]*>",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_LINE_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class AnchorSlice:
    file: str
    start_anchor: str
    end_anchor: str | None
    text: str
    start_offset: int
    end_offset: int


def _read_zip_text(zip_file: ZipFile, file_path: str) -> str | None:
    try:
        raw = zip_file.read(file_path)
    except KeyError:
        return None
    return raw.decode("utf-8", errors="ignore")


def _anchor_pattern(anchor: str) -> re.Pattern[str]:
    escaped = re.escape(anchor)
    return re.compile(rf"""id\s*=\s*["']{escaped}["']""", re.IGNORECASE)


def find_anchor_start(content: str, anchor: str) -> int | None:
    match = _anchor_pattern(anchor).search(content)
    if match is None:
        return None
    return match.start()


def find_anchor_end(content: str, start_offset: int, end_anchor: str | None) -> int:
    if end_anchor is None:
        return len(content)
    if start_offset >= len(content):
        return len(content)
    match = _anchor_pattern(end_anchor).search(content, pos=max(0, start_offset))
    if match is None:
        return len(content)
    return match.start()


def _is_noise_line(line: str) -> bool:
    lower = line.strip().lower()
    if not lower:
        return True
    if re.fullmatch(r"\d+", lower):
        return True
    if re.fullmatch(r"chapter\s+\d+\b.*", lower):
        return True
    if re.fullmatch(r"[•·\-\u2022\u2023\u2043\u2219鈥?]+", line.strip()):
        return True
    if lower in {"summary", "contents", "document outline"}:
        return True
    return False


def clean_extracted_text(raw_text: str) -> str:
    with_breaks = _TAG_BLOCK_BREAK_RE.sub("\n", raw_text)
    without_tags = _TAG_RE.sub(" ", with_breaks)
    decoded = html.unescape(without_tags)
    decoded = decoded.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in decoded.split("\n")]

    cleaned_lines: list[str] = []
    for line in lines:
        normalized = _LINE_SPACE_RE.sub(" ", line).strip()
        if _is_noise_line(normalized):
            continue
        cleaned_lines.append(normalized)

    deduped_lines: list[str] = []
    previous = ""
    for line in cleaned_lines:
        if line == previous:
            continue
        deduped_lines.append(line)
        previous = line

    return "\n".join(deduped_lines).strip()


def extract_text_between_anchors(
    content: str,
    start_anchor: str,
    end_anchor: str | None,
) -> tuple[str, int, int] | None:
    start_offset = find_anchor_start(content, start_anchor)
    if start_offset is None:
        return None

    start_tag_close = content.find(">", start_offset)
    body_start = start_tag_close + 1 if start_tag_close >= 0 else start_offset
    end_offset = find_anchor_end(content, body_start, end_anchor)
    if end_offset < body_start:
        end_offset = len(content)

    raw_slice = content[body_start:end_offset]
    cleaned = clean_extracted_text(raw_slice)
    if not cleaned:
        return None
    return cleaned, start_offset, end_offset


def extract_anchor_slice(
    zip_file: ZipFile,
    file_path: str,
    start_anchor: str,
    end_anchor: str | None = None,
) -> AnchorSlice | None:
    content = _read_zip_text(zip_file, file_path)
    if content is None:
        return None

    extracted = extract_text_between_anchors(
        content=content,
        start_anchor=start_anchor,
        end_anchor=end_anchor,
    )
    if extracted is None:
        return None
    text, start_offset, end_offset = extracted
    return AnchorSlice(
        file=file_path,
        start_anchor=start_anchor,
        end_anchor=end_anchor,
        text=text,
        start_offset=start_offset,
        end_offset=end_offset,
    )


def extract_anchor_slice_from_epub(
    epub_path: str | Path,
    file_path: str,
    start_anchor: str,
    end_anchor: str | None = None,
) -> AnchorSlice | None:
    with ZipFile(Path(epub_path)) as zip_file:
        return extract_anchor_slice(
            zip_file=zip_file,
            file_path=file_path,
            start_anchor=start_anchor,
            end_anchor=end_anchor,
        )
