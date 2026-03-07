from pathlib import Path

TARGET_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".ts", ".js"}


def main() -> int:
    failed: list[str] = []
    for path in Path(".").rglob("*"):
        if path.is_file() and path.suffix in TARGET_SUFFIXES:
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                failed.append(str(path))

    if failed:
        print("UTF-8 decode failed for:")
        for entry in failed:
            print(entry)
        return 1

    print("UTF-8 check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

