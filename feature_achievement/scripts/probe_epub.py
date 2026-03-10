import argparse
import json
import sys
from pathlib import Path

from feature_achievement.epub.probe import probe_epub


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe EPUB structure and select parser strategy.",
    )
    parser.add_argument(
        "--epub",
        required=True,
        help="Path to input EPUB file.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON output file path.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Fail with non-zero exit if confidence is below this value.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = probe_epub(args.epub)
    payload = result.as_dict()
    payload_json_console = json.dumps(payload, ensure_ascii=True, indent=2)
    print(payload_json_console)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload_json_file = json.dumps(payload, ensure_ascii=False, indent=2)
        output_path.write_text(payload_json_file + "\n", encoding="utf-8")

    if result.selected_strategy is None:
        print("probe failed: no parser strategy selected", file=sys.stderr)
        return 2
    if result.confidence < args.min_confidence:
        print(
            "probe confidence too low: "
            f"{result.confidence} < {args.min_confidence}",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
