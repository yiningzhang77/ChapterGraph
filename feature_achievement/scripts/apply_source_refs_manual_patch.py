import argparse
import json
from pathlib import Path
from typing import TypedDict


class ManualPatchItem(TypedDict):
    chapter_id: str
    bullet_id: str
    source_refs: list[dict[str, object]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply manual source_refs patch onto enriched JSON.",
    )
    parser.add_argument(
        "--enriched",
        required=True,
        help="Path to enriched JSON file.",
    )
    parser.add_argument(
        "--patch",
        required=True,
        help="Path to manual patch JSON list.",
    )
    parser.add_argument(
        "--output",
        help="Path to write patched enriched JSON. Default: overwrite --enriched file.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_patch_items(raw: object) -> list[ManualPatchItem]:
    if not isinstance(raw, list):
        raise ValueError("patch JSON must be a list")

    items: list[ManualPatchItem] = []
    for index, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"patch row {index}: must be object")

        chapter_id = row.get("chapter_id")
        bullet_id = row.get("bullet_id")
        source_refs = row.get("source_refs")
        if not isinstance(chapter_id, str) or not chapter_id:
            raise ValueError(f"patch row {index}: chapter_id must be non-empty string")
        if not isinstance(bullet_id, str) or not bullet_id:
            raise ValueError(f"patch row {index}: bullet_id must be non-empty string")
        if not isinstance(source_refs, list) or not source_refs:
            raise ValueError(f"patch row {index}: source_refs must be non-empty list")
        for ref_index, source_ref in enumerate(source_refs, start=1):
            if not isinstance(source_ref, dict):
                raise ValueError(
                    f"patch row {index} source_refs[{ref_index}]: must be object"
                )

        items.append(
            {
                "chapter_id": chapter_id,
                "bullet_id": bullet_id,
                "source_refs": source_refs,
            }
        )
    items.sort(key=lambda item: (item["chapter_id"], item["bullet_id"]))
    return items


def _build_bullet_index(
    enriched_book: dict[str, object],
) -> dict[tuple[str, str], dict[str, object]]:
    chapters_obj = enriched_book.get("chapters")
    chapters = chapters_obj if isinstance(chapters_obj, list) else []

    index: dict[tuple[str, str], dict[str, object]] = {}
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_id_obj = chapter.get("id")
        if not isinstance(chapter_id_obj, str):
            continue
        sections_obj = chapter.get("sections")
        sections = sections_obj if isinstance(sections_obj, list) else []
        for section in sections:
            if not isinstance(section, dict):
                continue
            bullets_obj = section.get("bullets")
            bullets = bullets_obj if isinstance(bullets_obj, list) else []
            for bullet in bullets:
                if not isinstance(bullet, dict):
                    continue
                bullet_id_obj = bullet.get("bullet_id")
                if not isinstance(bullet_id_obj, str):
                    continue
                index[(chapter_id_obj, bullet_id_obj)] = bullet
    return index


def apply_manual_source_refs_patch(
    enriched_book: dict[str, object],
    patch_items: list[ManualPatchItem],
) -> dict[str, int]:
    bullet_index = _build_bullet_index(enriched_book)

    patched_count = 0
    skipped_existing_count = 0
    missing_count = 0

    for item in patch_items:
        key = (item["chapter_id"], item["bullet_id"])
        bullet = bullet_index.get(key)
        if bullet is None:
            missing_count += 1
            continue

        current_refs = bullet.get("source_refs")
        can_patch = current_refs is None or (
            isinstance(current_refs, list) and len(current_refs) == 0
        )
        if not can_patch:
            skipped_existing_count += 1
            continue

        bullet["source_refs"] = item["source_refs"]
        patched_count += 1

    return {
        "patched": patched_count,
        "skipped_existing": skipped_existing_count,
        "missing": missing_count,
    }


def main() -> int:
    args = parse_args()
    enriched_path = Path(args.enriched)
    patch_path = Path(args.patch)
    output_path = Path(args.output) if args.output else enriched_path

    enriched_raw = _load_json(enriched_path)
    if not isinstance(enriched_raw, dict):
        raise ValueError("enriched JSON must be an object")

    patch_items = _parse_patch_items(_load_json(patch_path))
    stats = apply_manual_source_refs_patch(enriched_raw, patch_items)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(enriched_raw, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"output_path={output_path}")
    print(f"patched={stats['patched']}")
    print(f"skipped_existing={stats['skipped_existing']}")
    print(f"missing={stats['missing']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
