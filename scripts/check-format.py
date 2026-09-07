from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CHECKED_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".ts",
    ".tsx",
    ".yml",
    ".yaml",
}
SKIPPED_PARTS = {
    ".git",
    ".venv",
    ".backend-venv",
    ".test-venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "backend/artifacts",
    "datasets/raw",
    "datasets/processed",
    "datasets/versions",
}


def should_skip(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in SKIPPED_PARTS or part.startswith((".backend-venv", ".test-cache")) for part in relative.parts):
        return True
    relative_text = relative.as_posix()
    return any(relative_text.startswith(skipped + "/") for skipped in SKIPPED_PARTS)


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    payload = path.read_bytes()
    if not payload:
        return errors
    relative = path.relative_to(ROOT)
    if b"\r\n" in payload:
        errors.append(f"{relative}: uses CRLF line endings")
    if not payload.endswith(b"\n"):
        errors.append(f"{relative}: missing final newline")
    for index, line in enumerate(payload.splitlines(), start=1):
        if line.rstrip(b" \t") != line:
            errors.append(f"{relative}:{index}: trailing whitespace")
        if b"\t" in line:
            errors.append(f"{relative}:{index}: contains tab character")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or should_skip(path) or path.suffix not in CHECKED_SUFFIXES:
            continue
        errors.extend(check_file(path))
    if errors:
        print("Formatting hygiene check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Formatting hygiene check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
