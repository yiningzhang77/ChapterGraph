import argparse
import json
import os

import yaml
from sqlmodel import Session

from feature_achievement.db.engine import engine
from feature_achievement.db.crud import persist_enriched_chapters

"""
Raw content
   ↓
ingestion.py 结构化
   ↓
enrichment.py 生成 enriched JSON   ← 这里是“计算层”
   ↓
📦 import_enriched_chapters.py     ← 这里是“数据入库层”
   ↓
DB: enriched_chapter 表
   ↓
embedding / edge 计算 / 可视化

"""


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def iter_enriched_books(config_path: str, output_dir: str):
    with open(config_path, "r", encoding="utf-8") as f:
        book_configs = yaml.safe_load(f) or []

    for cfg in book_configs:
        book_id = cfg["book_name"]
        json_path = os.path.join(output_dir, f"{book_id}_enriched.json")
        if not os.path.exists(json_path):
            print(f"skip: {json_path} not found")
            continue
        yield load_json(json_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import enriched chapters from output JSON into DB.",
    )
    parser.add_argument("--config", default="book_content/books.yaml")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--enrichment-version", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    enriched_books = list(iter_enriched_books(args.config, args.output_dir))
    if not enriched_books:
        print("No enriched JSON found. Run enrichment first.")
        return 1

    with Session(engine) as session:
        persist_enriched_chapters(
            enriched_books,
            session,
            enrichment_version=args.enrichment_version,
            overwrite=args.overwrite,
        )

    print(f"Imported enriched chapters for {len(enriched_books)} books.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
