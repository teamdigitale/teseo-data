#!/usr/bin/env python3
"""
Convert CSV rows to paragraphs in .txt format.

Each row becomes a paragraph:
  <column-name>: <cell-value>
  <column-name>: <cell-value>
  ...
  ===

Rows with any empty/undefined cell are skipped.

Usage:
  python csv_to_paragraphs.py [--input FILE] [--output FILE] [--separator SEP]
  python csv_to_paragraphs.py --input data/anonymized/output_case.csv --output data/anonymized/case_paragraphs.txt
"""

import argparse
import csv
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DEFAULT_INPUT = SCRIPT_DIR / "input" / "case.csv"
DEFAULT_OUTPUT = SCRIPT_DIR.parent.parent / "data" / "anonymized" / "case_paragraphs.txt"
DEFAULT_SEPARATOR = "==="


def is_empty(value: str) -> bool:
    """Consider None, empty string, or whitespace-only as empty."""
    if value is None:
        return True
    return not str(value).strip()


def row_to_paragraph(
    row: dict, separator: str, columns: list[str] | None = None
) -> str | None:
    """
    Convert a CSV row to paragraph format.
    Returns None if any relevant cell value is empty (row should be skipped).

    If columns is given, only those columns are included and required to be non-empty.
    Otherwise all columns are included and every cell must be non-empty.
    """
    keys = columns if columns is not None else list(row.keys())
    lines = []
    for col in keys:
        val = row.get(col, "")
        if is_empty(val):
            return None
        lines.append(f"{col}: {val.strip()}")
    return "\n".join(lines) + "\n" + separator


def csv_to_paragraphs(
    input_path: Path,
    output_path: Path,
    separator: str = DEFAULT_SEPARATOR,
    columns: list[str] | None = None,
) -> tuple[int, int]:
    """
    Read CSV, write paragraphs to .txt.
    Returns (rows_read, paragraphs_written).

    If columns is set, only those columns are written and required to be non-empty.
    """
    rows_read = 0
    paragraphs_written = 0
    paragraphs = []

    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            rows_read += 1
            ordered_row = {k: row.get(k, "") for k in fieldnames}
            if columns is not None:
                ordered_row = {k: ordered_row.get(k, "") for k in columns}
            block = row_to_paragraph(ordered_row, separator, columns)
            if block is not None:
                paragraphs.append(block)
                paragraphs_written += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(paragraphs))
        if paragraphs:
            f.write("\n")

    return rows_read, paragraphs_written


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert CSV rows to paragraphs (col: value) in a .txt file.",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input CSV path (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output .txt path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--separator",
        "-s",
        type=str,
        default=DEFAULT_SEPARATOR,
        help=f"Paragraph separator (default: {DEFAULT_SEPARATOR!r})",
    )
    parser.add_argument(
        "--columns",
        "-c",
        type=str,
        default=None,
        metavar="COL1,COL2,...",
        help="Use only these columns (comma-separated). Row is skipped only if one of these is empty.",
    )
    args = parser.parse_args()

    columns = None
    if args.columns:
        columns = [c.strip() for c in args.columns.split(",") if c.strip()]

    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        return 1

    rows_read, paragraphs_written = csv_to_paragraphs(
        args.input, args.output, args.separator, columns=columns
    )
    print(f"Read {rows_read} rows, wrote {paragraphs_written} paragraphs to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
