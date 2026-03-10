import argparse
import json
from pathlib import Path

from feature_achievement.epub.adapter import build_adapter_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build enriched v2 JSON from an EPUB file.",
    )
    parser.add_argument(
        "--epub",
        required=True,
        help="Path to EPUB file.",
    )
    parser.add_argument(
        "--book-id",
        required=True,
        help="Book id used to build chapter ids.",
    )
    parser.add_argument(
        "--output",
        help="Output JSON path. Default: output/{book_id}_enriched_from_epub.json",
    )
    parser.add_argument(
        "--unresolved-output",
        default="tmp/source_refs_needs_manual.json",
        help=(
            "Path to write unresolved source ref items for manual backfill. "
            "Default: tmp/source_refs_needs_manual.json"
        ),
    )
    parser.add_argument(
        "--include-appendix",
        action="store_true",
        help="Include appendix-like chapter entries (A/B/... or Appendix ...).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_adapter_payload(
        epub_path=args.epub,
        book_id=args.book_id,
        include_appendix=args.include_appendix,
    )
    chapters = payload["chapters"]
    metrics = payload["metrics"]
    unresolved = payload["unresolved_source_refs"]

    if not chapters:
        print("no chapters were produced from EPUB")
        return 1

    parse_status = "ok" if not unresolved else "ok_with_unresolved"
    output_json: dict[str, object] = {
        "book_id": args.book_id,
        "chapters": chapters,
        "parse_status": parse_status,
        "parse_metrics": metrics,
        "probe": payload["probe"],
        "unresolved_source_refs": unresolved,
    }

    output_path = (
        Path(args.output)
        if args.output
        else Path("output") / f"{args.book_id}_enriched_from_epub.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    unresolved_output_path = Path(args.unresolved_output)
    unresolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    unresolved_output_path.write_text(
        json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"output_path={output_path}")
    print(f"unresolved_output_path={unresolved_output_path}")
    print(f"parse_status={parse_status}")
    print(f"chapter_count={metrics['chapter_count']}")
    print(f"section_count={metrics['section_count']}")
    print(f"bullet_count={metrics['bullet_count']}")
    print(f"bullets_with_source_refs={metrics['bullets_with_source_refs']}")
    print(f"unresolved_source_refs={metrics['unresolved_source_refs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
