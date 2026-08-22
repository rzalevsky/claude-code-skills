#!/usr/bin/env python3
"""Validate an extracted record against a JSON Schema, with the locale fixes that
silently corrupt data when they are missing.

The contract this script enforces: nothing doubtful reaches the system of record.
On any failure it prints what failed, echoes the raw input so the failure is
diagnosable without digging up the source document, and exits non-zero so the
surrounding workflow step fails instead of passing a partial record downstream.

Usage:
    python3 validate_extraction.py --schema schema.json --data extracted.json
    python3 validate_extraction.py --schema schema.json --data extracted.json --normalise
    cat model_output.txt | python3 validate_extraction.py --schema schema.json --normalise

--normalise applies, before validation:
    * strips markdown code fences the model wrapped around the JSON
    * "1 234,56" / "1.234,56" -> 1234.56   (decimal comma, thousands separators, NBSP)
    * "03.04.2026" / "2026-04-03"          -> ISO date, refusing genuinely ambiguous input
    * trims whitespace in strings

Exit codes: 0 = valid, 1 = validation failed, 2 = could not read input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date

try:
    import jsonschema

    # Pick the newest validator this installation actually has. jsonschema 3.x - still
    # what many distributions ship - has no Draft202012Validator, and assuming it is
    # there turns a missing optional dependency into a crash on somebody else's machine.
    VALIDATOR_CLASS = next(
        (getattr(jsonschema, name) for name in
         ("Draft202012Validator", "Draft201909Validator", "Draft7Validator", "Draft4Validator")
         if hasattr(jsonschema, name)), None)
    HAVE_JSONSCHEMA = VALIDATOR_CLASS is not None
except ImportError:  # pragma: no cover
    VALIDATOR_CLASS = None
    HAVE_JSONSCHEMA = False

NBSP = " "
THIN_SPACE = " "


def strip_fences(text: str) -> str:
    """Models wrap JSON in code fences no matter what the prompt says."""
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    return fence.group(1) if fence else text


def normalise_number(value):
    """Turn a locale-formatted amount into a float, or raise with a readable reason.

    The case this exists for: a Polish-language model returns "123,45". float() throws,
    and code that splits on the comma books 123. Both are worse than a clear error.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        raise ValueError(f"expected a number, got {type(value).__name__}")

    raw = value.strip().replace(NBSP, "").replace(THIN_SPACE, "").replace(" ", "")
    raw = re.sub(r"[^\d,.\-+]", "", raw)  # drop currency symbols and stray letters
    if not raw:
        raise ValueError(f"no digits in {value!r}")

    has_comma, has_dot = "," in raw, "." in raw
    if has_comma and has_dot:
        # Whichever separator comes last is the decimal one: 1.234,56 vs 1,234.56
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif has_comma:
        # A single comma is a decimal comma unless it groups exactly three digits
        # AND appears more than once - "1,234" alone is genuinely ambiguous, and we
        # treat it as a decimal comma because that is the local convention here.
        raw = raw.replace(",", ".") if raw.count(",") == 1 else raw.replace(",", "")

    try:
        return float(raw)
    except ValueError as err:
        raise ValueError(f"cannot parse {value!r} as a number: {err}") from None


DATE_PATTERNS = [
    (re.compile(r"^(\d{4})-(\d{2})-(\d{2})$"), ("y", "m", "d")),
    (re.compile(r"^(\d{4})/(\d{2})/(\d{2})$"), ("y", "m", "d")),
    (re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$"), ("d", "m", "y")),   # 03.04.2026 - PL/DE
    (re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$"), ("d", "m", "y")),
]


def normalise_date(value, assume_day_first: bool = True) -> str:
    """Return an ISO date, or raise. Ambiguous slash dates are refused, not guessed."""
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError(f"expected a date string, got {type(value).__name__}")
    raw = value.strip()

    for pattern, order in DATE_PATTERNS:
        match = pattern.match(raw)
        if match:
            parts = dict(zip(order, match.groups()))
            try:
                return date(int(parts["y"]), int(parts["m"]), int(parts["d"])).isoformat()
            except ValueError as err:
                raise ValueError(f"{value!r} is not a real date: {err}") from None

    slash = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
    if slash:
        first, second, year = (int(g) for g in slash.groups())
        if first > 12 or second > 12:  # unambiguous - one of them cannot be a month
            day, month = (first, second) if first > 12 else (second, first)
            return date(year, month, day).isoformat()
        if not assume_day_first:
            raise ValueError(
                f"{value!r} is ambiguous: 03/04 is 3 April in Warsaw and 4 March in Chicago. "
                f"Fail rather than guess, or pass the document locale explicitly."
            )
        return date(year, second, first).isoformat()

    raise ValueError(f"unrecognised date format: {value!r}. Require ISO YYYY-MM-DD from the model.")


def normalise(record: dict, schema: dict) -> tuple[dict, list]:
    """Apply locale fixes guided by the schema's declared types."""
    notes: list[str] = []
    properties = schema.get("properties", {})
    out = dict(record)

    for field, spec in properties.items():
        if field not in out or out[field] is None:
            continue
        declared = spec.get("type")
        value = out[field]

        if declared == "number" or declared == "integer":
            try:
                fixed = normalise_number(value)
            except ValueError as err:
                notes.append(f"{field}: {err}")
                continue
            if fixed != value:
                notes.append(f"{field}: {value!r} -> {fixed}")
            out[field] = int(fixed) if declared == "integer" else fixed

        elif declared == "string" and spec.get("format") == "date":
            try:
                fixed = normalise_date(value)
            except ValueError as err:
                notes.append(f"{field}: {err}")
                continue
            if fixed != value:
                notes.append(f"{field}: {value!r} -> {fixed}")
            out[field] = fixed

        elif declared == "string" and isinstance(value, str):
            stripped = value.strip()
            if stripped != value:
                notes.append(f"{field}: trimmed whitespace")
            out[field] = stripped

    return out, notes


def validate_without_jsonschema(record: dict, schema: dict) -> list:
    """Enough of JSON Schema to be useful when the library is not installed."""
    errors = []
    properties = schema.get("properties", {})

    for field in schema.get("required", []):
        if field not in record or record[field] is None:
            errors.append(f"required field missing or null: {field}")

    if schema.get("additionalProperties") is False:
        for field in record:
            if field not in properties:
                errors.append(f"unexpected field '{field}' - the model invented it, "
                              f"which usually means it misread the document")

    type_map = {"string": str, "number": (int, float), "integer": int,
                "boolean": bool, "array": list, "object": dict}
    for field, spec in properties.items():
        if field not in record or record[field] is None:
            continue
        value = record[field]
        expected = spec.get("type")
        if expected in type_map and not isinstance(value, type_map[expected]):
            errors.append(f"{field}: expected {expected}, got {type(value).__name__} ({value!r})")
            continue
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"{field}: {value!r} is not one of {spec['enum']}")
        if expected == "string":
            if "minLength" in spec and len(value) < spec["minLength"]:
                errors.append(f"{field}: shorter than minLength {spec['minLength']}")
            if spec.get("format") == "date":
                try:
                    normalise_date(value, assume_day_first=False)
                except ValueError as err:
                    errors.append(f"{field}: {err}")
        if expected in ("number", "integer"):
            if "exclusiveMinimum" in spec and value <= spec["exclusiveMinimum"]:
                errors.append(f"{field}: {value} must be greater than {spec['exclusiveMinimum']}")
            if "minimum" in spec and value < spec["minimum"]:
                errors.append(f"{field}: {value} is below minimum {spec['minimum']}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--schema", required=True, help="path to the JSON Schema")
    parser.add_argument("--data", help="path to the extracted JSON (default: stdin)")
    parser.add_argument("--normalise", action="store_true",
                        help="apply locale fixes for numbers and dates before validating")
    parser.add_argument("--out", help="write the normalised record here when it validates")
    args = parser.parse_args()

    try:
        with open(args.schema, encoding="utf-8") as handle:
            schema = json.load(handle)
    except (OSError, json.JSONDecodeError) as err:
        print(f"Cannot read schema: {err}", file=sys.stderr)
        return 2

    raw = open(args.data, encoding="utf-8").read() if args.data else sys.stdin.read()
    try:
        record = json.loads(strip_fences(raw))
    except json.JSONDecodeError as err:
        print("EXTRACTION FAILED: output is not valid JSON", file=sys.stderr)
        print(f"  {err}", file=sys.stderr)
        print("\n--- raw input ---", file=sys.stderr)
        print(raw[:2000], file=sys.stderr)
        return 1

    notes: list[str] = []
    if args.normalise:
        record, notes = normalise(record, schema)

    if HAVE_JSONSCHEMA:
        validator = VALIDATOR_CLASS(schema)
        errors = [f"{'.'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
                  for e in validator.iter_errors(record)]
        # Draft 7 and earlier ignore "format" unless a format checker is wired in, so the
        # date check would silently not run. Do it here rather than pretend it happened.
        if VALIDATOR_CLASS.__name__ in ("Draft7Validator", "Draft4Validator"):
            for field, spec in schema.get("properties", {}).items():
                if spec.get("format") == "date" and isinstance(record.get(field), str):
                    try:
                        normalise_date(record[field], assume_day_first=False)
                    except ValueError as err:
                        errors.append(f"{field}: {err}")
    else:
        errors = validate_without_jsonschema(record, schema)
        notes.append("jsonschema not available - using the built-in subset of checks. "
                     "Install it with `pip install jsonschema` for full coverage.")

    if errors:
        print("EXTRACTION FAILED: record does not satisfy the schema", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        if notes:
            print("\nnotes:", file=sys.stderr)
            for note in notes:
                print(f"  - {note}", file=sys.stderr)
        print("\n--- raw input ---", file=sys.stderr)
        print(raw[:2000], file=sys.stderr)
        print("\nDo not write this record. Route the document to a human queue instead - "
              "a partial or defaulted record is worse than a failed run.", file=sys.stderr)
        return 1

    if notes:
        print("VALID (with normalisation applied)")
        for note in notes:
            print(f"  - {note}")
    else:
        print("VALID")

    output = json.dumps(record, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(output + "\n")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
