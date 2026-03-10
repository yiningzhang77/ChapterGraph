from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree
from zipfile import ZipFile

from feature_achievement.epub.probe import ProbeResult, probe_epub

_HEADING_RE = re.compile(
    r"<h([1-3])(?P<attrs>[^>]*)>(?P<body>.*?)</h\1>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_HREF_ANCHOR_RE = re.compile(r"^(?P<file>[^#]*)(?:#(?P<anchor>.+))?$")
_CHAPTER_TEXT_FILE_RE = re.compile(r"(^|/)oebps/text/\d+\.x?html?$", re.IGNORECASE)
_CHAPTER_FILE_RE = re.compile(r"(^|/)oebps/ch\d+\.x?html?$", re.IGNORECASE)
_INDEX_SPLIT_RE = re.compile(r"(^|/)index_split_\d+\.html$", re.IGNORECASE)


@dataclass(frozen=True)
class TocNode:
    level: int
    title: str
    href_file: str
    href_anchor: str | None


class _AnchorListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ul_depth = 0
        self.pending_href: str | None = None
        self.pending_text_parts: list[str] = []
        self.items: list[tuple[int, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "ul":
            self.ul_depth += 1
            return
        if tag_lower != "a":
            return
        href = dict(attrs).get("href")
        if href is None:
            return
        self.pending_href = href.strip()
        self.pending_text_parts = []

    def handle_data(self, data: str) -> None:
        if self.pending_href is None:
            return
        text = data.strip()
        if text:
            self.pending_text_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower == "ul":
            self.ul_depth = max(0, self.ul_depth - 1)
            return
        if tag_lower != "a":
            return
        if self.pending_href is None:
            return
        text = " ".join(self.pending_text_parts).strip()
        if text:
            level = max(1, self.ul_depth)
            self.items.append((level, self.pending_href, text))
        self.pending_href = None
        self.pending_text_parts = []


def _read_zip_text(zip_file: ZipFile, file_path: str) -> str | None:
    try:
        raw = zip_file.read(file_path)
    except KeyError:
        return None
    return raw.decode("utf-8", errors="ignore")


def _normalize_posix_path(path_value: str) -> str:
    return str(PurePosixPath(path_value))


def _resolve_href(source_file: str, href: str) -> tuple[str, str | None]:
    match = _HREF_ANCHOR_RE.match(href.strip())
    if match is None:
        return _normalize_posix_path(source_file), None

    raw_file = match.group("file") or ""
    anchor = match.group("anchor")
    if raw_file:
        resolved = (PurePosixPath(source_file).parent / raw_file).as_posix()
    else:
        resolved = source_file
    return _normalize_posix_path(resolved), anchor


def _strip_tags(text: str) -> str:
    no_tags = _TAG_RE.sub(" ", text)
    no_tags = html.unescape(no_tags)
    return re.sub(r"\s+", " ", no_tags).strip()


def _parse_ncx(zip_file: ZipFile, ncx_path: str) -> list[TocNode]:
    content = _read_zip_text(zip_file, ncx_path)
    if content is None:
        return []
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return []

    nodes: list[TocNode] = []

    def walk(nav_point: ElementTree.Element, level: int) -> None:
        label_text = ""
        for child in nav_point:
            if child.tag.endswith("navLabel"):
                for leaf in child.iter():
                    if leaf.tag.endswith("text") and leaf.text:
                        label_text = leaf.text.strip()
                        break
                if label_text:
                    break

        href = ""
        for child in nav_point:
            if child.tag.endswith("content"):
                href = child.attrib.get("src", "").strip()
                break

        if href:
            href_file, href_anchor = _resolve_href(ncx_path, href)
            title = re.sub(r"\s+", " ", label_text).strip()
            if title:
                nodes.append(
                    TocNode(
                        level=max(1, level),
                        title=title,
                        href_file=href_file,
                        href_anchor=href_anchor,
                    )
                )

        for child in nav_point:
            if child.tag.endswith("navPoint"):
                walk(child, level + 1)

    nav_map = None
    for element in root.iter():
        if element.tag.endswith("navMap"):
            nav_map = element
            break
    if nav_map is not None:
        for nav_point in nav_map:
            if nav_point.tag.endswith("navPoint"):
                walk(nav_point, level=1)

    return nodes


def _parse_html_outline(zip_file: ZipFile, html_path: str) -> list[TocNode]:
    content = _read_zip_text(zip_file, html_path)
    if content is None:
        return []
    parser = _AnchorListParser()
    parser.feed(content)
    nodes: list[TocNode] = []
    for level, href, title in parser.items:
        href_file, href_anchor = _resolve_href(html_path, href)
        nodes.append(
            TocNode(
                level=level,
                title=title,
                href_file=href_file,
                href_anchor=href_anchor,
            )
        )
    return nodes


def _heading_level_from_title(title: str, html_level: int) -> int:
    if re.match(r"^\d+\.\d+\.\d+\b", title):
        return 3
    if re.match(r"^\d+\.\d+\b", title):
        return 2
    if re.match(r"^\d+\b", title):
        return 1
    return html_level


def _scan_body_headings(zip_file: ZipFile, html_path: str) -> list[TocNode]:
    content = _read_zip_text(zip_file, html_path)
    if content is None:
        return []

    nodes: list[TocNode] = []
    seen: set[tuple[int, str, str | None]] = set()
    for match in _HEADING_RE.finditer(content):
        html_level = int(match.group(1))
        attrs = match.group("attrs")
        body = match.group("body")
        title = _strip_tags(body)
        if not title:
            continue

        id_match = re.search(r"""id\s*=\s*["']([^"']+)["']""", attrs, re.IGNORECASE)
        anchor = id_match.group(1) if id_match else None
        level = _heading_level_from_title(title, html_level)

        key = (level, title, anchor)
        if key in seen:
            continue
        seen.add(key)
        nodes.append(
            TocNode(
                level=level,
                title=title,
                href_file=_normalize_posix_path(html_path),
                href_anchor=anchor,
            )
        )
    return nodes


def _dedupe_nodes(nodes: list[TocNode]) -> list[TocNode]:
    unique: list[TocNode] = []
    seen: set[tuple[int, str, str, str | None]] = set()
    for node in nodes:
        key = (node.level, node.title, node.href_file, node.href_anchor)
        if key in seen:
            continue
        seen.add(key)
        unique.append(node)
    return unique


def _extract_type_a(zip_file: ZipFile, probe_result: ProbeResult) -> list[TocNode]:
    for source in probe_result.toc_sources:
        if source.lower().endswith("index_split_008.html"):
            nodes = _parse_html_outline(zip_file, source)
            if nodes:
                return _dedupe_nodes(nodes)

    for source in probe_result.toc_sources:
        if source.lower().endswith(".ncx"):
            nodes = _parse_ncx(zip_file, source)
            if nodes:
                return _dedupe_nodes(nodes)

    fallback_nodes: list[TocNode] = []
    for file_path in zip_file.namelist():
        if _INDEX_SPLIT_RE.search(file_path):
            fallback_nodes.extend(_scan_body_headings(zip_file, file_path))
    return _dedupe_nodes(fallback_nodes)


def _extract_type_b(zip_file: ZipFile, probe_result: ProbeResult) -> list[TocNode]:
    for source in probe_result.toc_sources:
        if source.lower().endswith(".ncx"):
            nodes = _parse_ncx(zip_file, source)
            if nodes:
                return _dedupe_nodes(nodes)

    for source in zip_file.namelist():
        if source.lower().endswith("spilca_toc.htm"):
            nodes = _parse_html_outline(zip_file, source)
            if nodes:
                return _dedupe_nodes(nodes)

    fallback_nodes: list[TocNode] = []
    for file_path in zip_file.namelist():
        if _CHAPTER_FILE_RE.search(file_path):
            fallback_nodes.extend(_scan_body_headings(zip_file, file_path))
    return _dedupe_nodes(fallback_nodes)


def _extract_type_c(zip_file: ZipFile, probe_result: ProbeResult) -> list[TocNode]:
    base_nodes: list[TocNode] = []
    for source in probe_result.toc_sources:
        lower = source.lower()
        if lower.endswith(".ncx"):
            base_nodes = _parse_ncx(zip_file, source)
            if base_nodes:
                break
    if not base_nodes:
        for source in probe_result.toc_sources:
            if source.lower().endswith("navdisplay.html"):
                base_nodes = _parse_html_outline(zip_file, source)
                if base_nodes:
                    break

    chapter_files = sorted(
        {
            node.href_file
            for node in base_nodes
            if _CHAPTER_TEXT_FILE_RE.search(node.href_file)
        }
    )
    if not chapter_files:
        chapter_files = [
            file_path
            for file_path in zip_file.namelist()
            if _CHAPTER_TEXT_FILE_RE.search(file_path)
        ]

    heading_nodes_by_file: dict[str, list[TocNode]] = {}
    for chapter_file in chapter_files:
        heading_nodes_by_file[chapter_file] = [
            node
            for node in _scan_body_headings(zip_file, chapter_file)
            if node.level >= 2
        ]

    ordered_nodes: list[TocNode] = []
    injected_files: set[str] = set()
    for node in base_nodes:
        ordered_nodes.append(node)
        file_path = node.href_file
        if file_path in injected_files:
            continue
        chapter_headings = heading_nodes_by_file.get(file_path)
        if chapter_headings:
            ordered_nodes.extend(chapter_headings)
            injected_files.add(file_path)

    for chapter_file in chapter_files:
        if chapter_file in injected_files:
            continue
        ordered_nodes.extend(heading_nodes_by_file.get(chapter_file, []))

    return _dedupe_nodes(ordered_nodes)


def extract_outline(epub_path: str | Path, probe_result: ProbeResult | None = None) -> list[TocNode]:
    result = probe_result if probe_result is not None else probe_epub(epub_path)
    with ZipFile(Path(epub_path)) as zip_file:
        if result.content_layout_type == "type_a_split_pages":
            return _extract_type_a(zip_file, result)
        if result.content_layout_type == "type_b_chapter_files":
            return _extract_type_b(zip_file, result)
        if result.content_layout_type == "type_c_text_dir_chapters":
            return _extract_type_c(zip_file, result)
    return []
