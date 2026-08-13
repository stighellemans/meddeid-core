"""Command-line canonicalization for MedDeID JSONL records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .normalize import normalize_record


def normalize_jsonl_text(text: str, *, source: str = "<input>") -> str:
    rows: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in {source} on line {line_number}: {error}") from error
        if not isinstance(raw, dict):
            raise ValueError(f"Expected a JSON object in {source} on line {line_number}")
        rows.append(json.dumps(normalize_record(raw), ensure_ascii=False, separators=(",", ":")))
    return "\n".join(rows) + ("\n" if rows else "")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Canonicalize supported MedDeID JSONL field variants.",
    )
    parser.add_argument("input", help="input JSONL path, or - for standard input")
    parser.add_argument("output", help="output JSONL path, or - for standard output")
    args = parser.parse_args()

    if args.input != "-" and args.output != "-":
        input_path = Path(args.input).resolve()
        output_path = Path(args.output).resolve()
        if input_path == output_path:
            parser.error("input and output must differ; write to a new file and verify it first")

    if args.input == "-":
        source = "<stdin>"
        raw_text = sys.stdin.read()
    else:
        input_path = Path(args.input)
        source = str(input_path)
        raw_text = input_path.read_text(encoding="utf-8")

    normalized = normalize_jsonl_text(raw_text, source=source)
    if args.output == "-":
        sys.stdout.write(normalized)
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(normalized, encoding="utf-8")


if __name__ == "__main__":
    main()
