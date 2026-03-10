from pathlib import Path

from feature_achievement.epub.adapter import build_adapter_payload

UNRESOLVED_OUTPUT = Path("tmp/source_refs_needs_manual.json")


def _first_epub(folder: str) -> Path:
    candidates = sorted((Path("book_epub") / folder).glob("*.epub"))
    if not candidates:
        raise RuntimeError(f"missing sample epub under book_epub/{folder}")
    return candidates[0]


def _as_int(metrics: dict[str, object], key: str) -> int:
    value = metrics.get(key)
    if isinstance(value, int):
        return value
    raise RuntimeError(f"invalid metrics.{key}: {value}")


def main() -> int:
    samples = [
        {
            "folder": "spring_in_action",
            "book_id": "spring-in-action",
            "expected_type": "type_a_split_pages",
            "expected_strategy": "strategy_type_a_split_pages",
            "min_ratio": 0.7,
        },
        {
            "folder": "spring_start_here",
            "book_id": "spring-start-here",
            "expected_type": "type_b_chapter_files",
            "expected_strategy": "strategy_type_b_chapter_files",
            "min_ratio": 0.7,
        },
        {
            "folder": "springboot_in_action",
            "book_id": "springboot-in-action",
            "expected_type": "type_c_text_dir_chapters",
            "expected_strategy": "strategy_type_c_text_dir_chapters",
            "min_ratio": 0.6,
        },
    ]

    failures: list[str] = []
    unresolved_aggregate: list[dict[str, object]] = []

    for sample in samples:
        epub_path = _first_epub(sample["folder"])
        payload = build_adapter_payload(epub_path=epub_path, book_id=sample["book_id"])

        probe = payload["probe"]
        content_layout_type = probe.get("content_layout_type")
        strategy = probe.get("selected_strategy")
        if content_layout_type != sample["expected_type"]:
            failures.append(
                f"{sample['folder']}: layout mismatch "
                f"{content_layout_type} != {sample['expected_type']}"
            )
        if strategy != sample["expected_strategy"]:
            failures.append(
                f"{sample['folder']}: strategy mismatch "
                f"{strategy} != {sample['expected_strategy']}"
            )

        metrics = payload["metrics"]
        bullet_count = _as_int(metrics, "bullet_count")
        bullets_with_refs = _as_int(metrics, "bullets_with_source_refs")
        ratio = (bullets_with_refs / bullet_count) if bullet_count > 0 else 0.0
        if ratio < sample["min_ratio"]:
            failures.append(
                f"{sample['folder']}: source_ref coverage too low "
                f"{ratio:.3f} < {sample['min_ratio']:.3f}"
            )

        unresolved = payload["unresolved_source_refs"]
        for row in unresolved:
            enriched_row = dict(row)
            enriched_row["sample_folder"] = sample["folder"]
            unresolved_aggregate.append(enriched_row)

        print(
            f"{sample['folder']} -> type={content_layout_type}, strategy={strategy}, "
            f"bullet_count={bullet_count}, bullets_with_refs={bullets_with_refs}, "
            f"coverage={ratio:.3f}"
        )

    UNRESOLVED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    import json

    UNRESOLVED_OUTPUT.write_text(
        json.dumps(unresolved_aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"unresolved_output={UNRESOLVED_OUTPUT}")
    print(f"unresolved_count={len(unresolved_aggregate)}")

    if failures:
        print("smoke failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
