from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Literal
from xml.etree import ElementTree
from zipfile import ZipFile

ContentLayoutType = Literal[
    "type_a_split_pages",
    "type_b_chapter_files",
    "type_c_text_dir_chapters",
    "unknown",
]
AnchorStyle = Literal["pNN", "sigil_toc_id", "heading_id", "mixed", "unknown"]

_INDEX_SPLIT_RE = re.compile(r"(^|/)index_split_\d+\.html$", re.IGNORECASE)
_CHAPTER_FILE_RE = re.compile(r"(^|/)oebps/ch\d+\.x?html?$", re.IGNORECASE)
_TEXT_CHAPTER_RE = re.compile(r"(^|/)oebps/text/\d+\.x?html?$", re.IGNORECASE)
_TOC_HREF_ANCHOR_RE = re.compile(r"""(?:href|src)\s*=\s*["'][^"'#]+#([^"'#]+)""")


@dataclass(frozen=True)
class ProbeResult:
    epub_path: str
    epub_version: str
    rootfile_path: str | None
    toc_sources: list[str]
    content_layout_type: ContentLayoutType
    anchor_style: AnchorStyle
    chapter_file_pattern: str | None
    chapter_file_count: int
    total_file_count: int
    confidence: float
    selected_strategy: str | None
    notes: list[str]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_zip_text(zip_file: ZipFile, file_path: str) -> str | None:
    try:
        raw = zip_file.read(file_path)
    except KeyError:
        return None
    return raw.decode("utf-8", errors="ignore")


def _resolve_relative_path(base_file: str, href: str) -> str:
    base_dir = PurePosixPath(base_file).parent
    resolved = (base_dir / href).as_posix()
    return str(PurePosixPath(resolved))


def _parse_rootfile_path(zip_file: ZipFile) -> str | None:
    container_text = _read_zip_text(zip_file, "META-INF/container.xml")
    if container_text is None:
        return "content.opf" if "content.opf" in zip_file.namelist() else None

    try:
        root = ElementTree.fromstring(container_text)
    except ElementTree.ParseError:
        return "content.opf" if "content.opf" in zip_file.namelist() else None

    for node in root.iter():
        if node.tag.endswith("rootfile"):
            full_path = node.attrib.get("full-path")
            if full_path:
                return full_path
    return "content.opf" if "content.opf" in zip_file.namelist() else None


def _parse_epub_version(zip_file: ZipFile, rootfile_path: str | None) -> str:
    if rootfile_path is None:
        return "unknown"

    opf_text = _read_zip_text(zip_file, rootfile_path)
    if opf_text is None:
        return "unknown"
    try:
        root = ElementTree.fromstring(opf_text)
    except ElementTree.ParseError:
        return "unknown"

    version = root.attrib.get("version", "").strip()
    if version.startswith("3"):
        return "epub3"
    if version.startswith("2"):
        return "epub2"
    return "unknown"


def _parse_toc_sources(zip_file: ZipFile, rootfile_path: str | None) -> list[str]:
    sources: list[str] = []
    namelist = zip_file.namelist()

    if rootfile_path is not None:
        opf_text = _read_zip_text(zip_file, rootfile_path)
        if opf_text is not None:
            try:
                root = ElementTree.fromstring(opf_text)
            except ElementTree.ParseError:
                root = None

            if root is not None:
                for item in root.iter():
                    if not item.tag.endswith("item"):
                        continue
                    href = item.attrib.get("href")
                    if not href:
                        continue
                    media_type = item.attrib.get("media-type", "").strip().lower()
                    properties = item.attrib.get("properties", "").strip().lower()
                    full_path = _resolve_relative_path(rootfile_path, href)
                    is_nav = "nav" in properties
                    is_ncx = media_type == "application/x-dtbncx+xml" or href.lower().endswith(
                        ".ncx"
                    )
                    if (is_nav or is_ncx) and full_path in namelist:
                        sources.append(full_path)

    for candidate in ("toc.ncx", "OEBPS/toc.ncx"):
        if candidate in namelist and candidate not in sources:
            sources.append(candidate)

    for file_path in namelist:
        lower_name = file_path.lower()
        if not lower_name.endswith((".html", ".htm", ".xhtml")):
            continue
        if "index_split_008.html" in lower_name:
            text = _read_zip_text(zip_file, file_path) or ""
            if "document outline" in text.lower() and file_path not in sources:
                sources.append(file_path)
        if lower_name.endswith("navdisplay.html") and file_path not in sources:
            sources.append(file_path)

    return sources


def _detect_layout_type(namelist: list[str]) -> tuple[ContentLayoutType, str | None, int]:
    index_split_files = [name for name in namelist if _INDEX_SPLIT_RE.search(name)]
    if len(index_split_files) >= 5:
        return "type_a_split_pages", "index_split_*.html", len(index_split_files)

    chapter_files = [name for name in namelist if _CHAPTER_FILE_RE.search(name)]
    if len(chapter_files) >= 6:
        return "type_b_chapter_files", "OEBPS/chNN.htm", len(chapter_files)

    text_chapter_files = [name for name in namelist if _TEXT_CHAPTER_RE.search(name)]
    if len(text_chapter_files) >= 5:
        return "type_c_text_dir_chapters", "OEBPS/Text/NN.html", len(text_chapter_files)

    return "unknown", None, 0


def _collect_anchor_ids(zip_file: ZipFile, toc_sources: list[str]) -> list[str]:
    anchors: list[str] = []
    seen: set[str] = set()
    for source in toc_sources:
        text = _read_zip_text(zip_file, source)
        if text is None:
            continue
        for match in _TOC_HREF_ANCHOR_RE.finditer(text):
            anchor = match.group(1).strip()
            if anchor and anchor not in seen:
                seen.add(anchor)
                anchors.append(anchor)
    return anchors


def _detect_anchor_style(anchor_ids: list[str]) -> AnchorStyle:
    if not anchor_ids:
        return "unknown"

    pnn_count = 0
    sigil_count = 0
    heading_count = 0
    other_count = 0

    for anchor in anchor_ids:
        lower_anchor = anchor.lower()
        if re.fullmatch(r"p\d+", lower_anchor):
            pnn_count += 1
        elif lower_anchor.startswith("sigil_toc_id"):
            sigil_count += 1
        elif lower_anchor.startswith("heading_id") or lower_anchor.startswith("id_"):
            heading_count += 1
        else:
            other_count += 1

    non_zero = sum(1 for count in (pnn_count, sigil_count, heading_count) if count > 0)
    if non_zero > 1 or (non_zero >= 1 and other_count > 0):
        return "mixed"
    if pnn_count > 0:
        return "pNN"
    if sigil_count > 0:
        return "sigil_toc_id"
    if heading_count > 0:
        return "heading_id"
    return "mixed"


def _strategy_for_layout(layout: ContentLayoutType) -> str | None:
    strategy_map: dict[ContentLayoutType, str | None] = {
        "type_a_split_pages": "strategy_type_a_split_pages",
        "type_b_chapter_files": "strategy_type_b_chapter_files",
        "type_c_text_dir_chapters": "strategy_type_c_text_dir_chapters",
        "unknown": None,
    }
    return strategy_map[layout]


def _compute_confidence(
    layout: ContentLayoutType,
    chapter_file_count: int,
    toc_source_count: int,
    anchor_style: AnchorStyle,
    rootfile_path: str | None,
) -> float:
    base_confidence: dict[ContentLayoutType, float] = {
        "type_a_split_pages": 0.86,
        "type_b_chapter_files": 0.84,
        "type_c_text_dir_chapters": 0.82,
        "unknown": 0.2,
    }
    confidence = base_confidence[layout]

    if chapter_file_count >= 10:
        confidence += 0.06
    elif chapter_file_count >= 5:
        confidence += 0.03

    if toc_source_count >= 2:
        confidence += 0.05
    elif toc_source_count == 1:
        confidence += 0.03

    if anchor_style != "unknown":
        confidence += 0.02
    if rootfile_path is None:
        confidence -= 0.08

    return round(max(0.0, min(0.99, confidence)), 3)


def probe_epub(epub_path: str | Path) -> ProbeResult:
    path = Path(epub_path)
    if not path.exists():
        raise FileNotFoundError(f"EPUB not found: {path}")
    if path.suffix.lower() != ".epub":
        raise ValueError(f"Not an EPUB file: {path}")

    notes: list[str] = []
    with ZipFile(path) as zip_file:
        namelist = zip_file.namelist()
        rootfile_path = _parse_rootfile_path(zip_file)
        epub_version = _parse_epub_version(zip_file, rootfile_path)
        toc_sources = _parse_toc_sources(zip_file, rootfile_path)
        layout, chapter_pattern, chapter_file_count = _detect_layout_type(namelist)
        anchor_ids = _collect_anchor_ids(zip_file, toc_sources)
        anchor_style = _detect_anchor_style(anchor_ids)
        selected_strategy = _strategy_for_layout(layout)
        confidence = _compute_confidence(
            layout=layout,
            chapter_file_count=chapter_file_count,
            toc_source_count=len(toc_sources),
            anchor_style=anchor_style,
            rootfile_path=rootfile_path,
        )

    if rootfile_path is None:
        notes.append("rootfile_path_missing")
    if not toc_sources:
        notes.append("toc_source_missing")
    if selected_strategy is None:
        notes.append("no_strategy_selected")
    if anchor_style == "unknown":
        notes.append("anchor_style_unknown")

    return ProbeResult(
        epub_path=str(path),
        epub_version=epub_version,
        rootfile_path=rootfile_path,
        toc_sources=toc_sources,
        content_layout_type=layout,
        anchor_style=anchor_style,
        chapter_file_pattern=chapter_pattern,
        chapter_file_count=chapter_file_count,
        total_file_count=len(namelist),
        confidence=confidence,
        selected_strategy=selected_strategy,
        notes=notes,
    )
