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
    row: dict,
    separator: str,
    require_columns: list[str] | None = None,
    output_columns: list[str] | None = None,
) -> str | None:
    """
    Convert a CSV row to paragraph format.
    Returns None if any required cell is empty (row should be skipped).

    - require_columns: row is skipped if any of these is empty. If None and output_columns
      is set, those are required; if both None, all columns are required.
    - output_columns: columns to write in the paragraph. If None, all keys from row.
    """
    out_cols = output_columns if output_columns is not None else list(row.keys())
    require = require_columns if require_columns is not None else out_cols

    for col in require:
        if is_empty(row.get(col, "")):
            return None
    lines = [f"{col}: {(row.get(col, '') or '').strip()}" for col in out_cols]
    return "\n".join(lines) + "\n" + separator


def csv_to_paragraphs(
    input_path: Path,
    output_path: Path,
    separator: str = DEFAULT_SEPARATOR,
    columns: list[str] | None = None,
    require_columns: list[str] | None = None,
) -> tuple[int, int]:
    """
    Read CSV, write paragraphs to .txt.
    Returns (rows_read, paragraphs_written).

    - columns: deprecated, use require_columns + output all columns. If set, only these
      columns are required and written (backward compatible).
    - require_columns: row included only if these columns are non-empty. Output: all
      CSV columns. Use with columns=None to get all columns in output.
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
                # Backward compat: require and output only these
                block = row_to_paragraph(
                    ordered_row, separator, require_columns=columns, output_columns=columns
                )
            else:
                # Require only require_columns (if set), output all columns
                block = row_to_paragraph(
                    ordered_row,
                    separator,
                    require_columns=require_columns or fieldnames,
                    output_columns=fieldnames,
                )
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
        help="(Deprecated) Require and output only these columns. Prefer --require and output all.",
    )
    parser.add_argument(
        "--require",
        "-r",
        type=str,
        default=None,
        metavar="COL1,COL2,...",
        help="Require these columns non-empty to include row. Output: all CSV columns.",
    )
    args = parser.parse_args()

    columns = None
    if args.columns:
        columns = [c.strip() for c in args.columns.split(",") if c.strip()]
    require_columns = None
    if args.require:
        require_columns = [c.strip() for c in args.require.split(",") if c.strip()]

    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        return 1

    rows_read, paragraphs_written = csv_to_paragraphs(
        args.input,
        args.output,
        args.separator,
        columns=columns,
        require_columns=require_columns,
    )
    print(f"Read {rows_read} rows, wrote {paragraphs_written} paragraphs to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
