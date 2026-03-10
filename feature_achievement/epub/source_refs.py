from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, NotRequired, TypedDict
from zipfile import ZipFile

from feature_achievement.epub.content import AnchorSlice, extract_anchor_slice

SOURCE_REF_FORMAT = "epub_anchor_v1"


class SourceSelector(TypedDict):
    type: Literal["id_range"]
    start: str
    end: str | None


class SourceRef(TypedDict):
    format: Literal["epub_anchor_v1"]
    file: str
    start_anchor: str
    end_anchor: str | None
    selector: SourceSelector
    snippet: str
    confidence: float
    origin: NotRequired[str]


def _compact_snippet(text: str, max_chars: int = 480) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def build_source_ref(
    *,
    file_path: str,
    start_anchor: str,
    end_anchor: str | None,
    snippet: str,
    confidence: float,
    origin: str = "auto",
) -> SourceRef:
    normalized_confidence = max(0.0, min(1.0, round(confidence, 3)))
    selector: SourceSelector = {
        "type": "id_range",
        "start": start_anchor,
        "end": end_anchor,
    }
    ref: SourceRef = {
        "format": SOURCE_REF_FORMAT,
        "file": file_path,
        "start_anchor": start_anchor,
        "end_anchor": end_anchor,
        "selector": selector,
        "snippet": _compact_snippet(snippet),
        "confidence": normalized_confidence,
    }
    if origin:
        ref["origin"] = origin
    return ref


def source_ref_from_slice(
    anchor_slice: AnchorSlice,
    *,
    confidence: float,
    origin: str = "auto",
) -> SourceRef:
    return build_source_ref(
        file_path=anchor_slice.file,
        start_anchor=anchor_slice.start_anchor,
        end_anchor=anchor_slice.end_anchor,
        snippet=anchor_slice.text,
        confidence=confidence,
        origin=origin,
    )


def build_source_refs_for_range(
    *,
    zip_file: ZipFile,
    file_path: str,
    start_anchor: str,
    end_anchor: str | None,
    confidence: float = 0.93,
    origin: str = "auto",
) -> list[SourceRef] | None:
    anchor_slice = extract_anchor_slice(
        zip_file=zip_file,
        file_path=file_path,
        start_anchor=start_anchor,
        end_anchor=end_anchor,
    )
    if anchor_slice is None:
        return None
    return [source_ref_from_slice(anchor_slice, confidence=confidence, origin=origin)]


def build_source_refs_with_fallback(
    *,
    zip_file: ZipFile,
    file_path: str,
    bullet_start_anchor: str,
    bullet_end_anchor: str | None,
    section_start_anchor: str | None = None,
    section_end_anchor: str | None = None,
    bullet_confidence: float = 0.93,
    section_confidence: float = 0.72,
) -> tuple[list[SourceRef] | None, str]:
    bullet_refs = build_source_refs_for_range(
        zip_file=zip_file,
        file_path=file_path,
        start_anchor=bullet_start_anchor,
        end_anchor=bullet_end_anchor,
        confidence=bullet_confidence,
        origin="auto",
    )
    if bullet_refs is not None:
        return bullet_refs, "bullet"

    if section_start_anchor is None:
        return None, "unresolved"

    section_refs = build_source_refs_for_range(
        zip_file=zip_file,
        file_path=file_path,
        start_anchor=section_start_anchor,
        end_anchor=section_end_anchor,
        confidence=section_confidence,
        origin="section_fallback",
    )
    if section_refs is None:
        return None, "unresolved"
    return section_refs, "section_fallback"


def build_source_refs_for_range_from_epub(
    *,
    epub_path: str | Path,
    file_path: str,
    start_anchor: str,
    end_anchor: str | None,
    confidence: float = 0.93,
    origin: str = "auto",
) -> list[SourceRef] | None:
    with ZipFile(Path(epub_path)) as zip_file:
        return build_source_refs_for_range(
            zip_file=zip_file,
            file_path=file_path,
            start_anchor=start_anchor,
            end_anchor=end_anchor,
            confidence=confidence,
            origin=origin,
        )


def build_source_refs_with_fallback_from_epub(
    *,
    epub_path: str | Path,
    file_path: str,
    bullet_start_anchor: str,
    bullet_end_anchor: str | None,
    section_start_anchor: str | None = None,
    section_end_anchor: str | None = None,
    bullet_confidence: float = 0.93,
    section_confidence: float = 0.72,
) -> tuple[list[SourceRef] | None, str]:
    with ZipFile(Path(epub_path)) as zip_file:
        return build_source_refs_with_fallback(
            zip_file=zip_file,
            file_path=file_path,
            bullet_start_anchor=bullet_start_anchor,
            bullet_end_anchor=bullet_end_anchor,
            section_start_anchor=section_start_anchor,
            section_end_anchor=section_end_anchor,
            bullet_confidence=bullet_confidence,
            section_confidence=section_confidence,
        )


def validate_source_ref_schema(ref: SourceRef) -> bool:
    required_keys = {
        "format",
        "file",
        "start_anchor",
        "end_anchor",
        "selector",
        "snippet",
        "confidence",
    }
    if not required_keys.issubset(ref.keys()):
        return False
    if ref["format"] != SOURCE_REF_FORMAT:
        return False
    selector = ref["selector"]
    if selector["type"] != "id_range":
        return False
    if selector["start"] != ref["start_anchor"]:
        return False
    if selector["end"] != ref["end_anchor"]:
        return False
    if not isinstance(ref["snippet"], str) or not ref["snippet"]:
        return False
    if not isinstance(ref["confidence"], float):
        return False
    return True
