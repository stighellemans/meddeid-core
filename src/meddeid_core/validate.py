"""Validation helpers for canonical DEID records (pure-python).

Two things matter most in practice and are cheap to check on every record:

* **offset integrity** — ``text[begin:end] == span.text``
* **label integrity** — ``label``/``category``/``subtype`` agree and are in the
  taxonomy.

``validate_record`` returns a list of human-readable problems (empty == OK).
"""

from __future__ import annotations

from typing import Any

from .taxonomy import compose_label, is_valid_category_subtype, is_valid_label, split_label


def check_offsets(record: dict[str, Any]) -> list[str]:
    """Verify each span's ``text`` matches ``record['text'][begin:end]``."""
    problems: list[str] = []
    text = record.get("text")
    if not isinstance(text, str):
        return problems  # nothing to check against (e.g. reid-only records)
    for i, span in enumerate(record.get("spans", []) or []):
        if not isinstance(span, dict):
            continue
        begin, end, span_text = span.get("begin"), span.get("end"), span.get("text")
        if not isinstance(begin, int) or not isinstance(end, int):
            problems.append(f"span[{i}]: non-integer begin/end ({begin!r}, {end!r})")
            continue
        if not (0 <= begin <= end <= len(text)):
            problems.append(f"span[{i}]: offsets out of range begin={begin} end={end} len={len(text)}")
            continue
        if span_text is not None and text[begin:end] != span_text:
            problems.append(
                f"span[{i}]: text mismatch — slice={text[begin:end]!r} span.text={span_text!r}"
            )
        subannotations = span.get("subannotations") or []
        if not isinstance(subannotations, list):
            problems.append(f"span[{i}].subannotations: expected a list")
            continue
        if subannotations:
            cursor = begin
            for j, item in enumerate(subannotations):
                prefix = f"span[{i}].subannotations[{j}]"
                if not isinstance(item, dict):
                    problems.append(f"{prefix}: expected an object")
                    continue
                sub_begin, sub_end = item.get("begin"), item.get("end")
                if not isinstance(sub_begin, int) or not isinstance(sub_end, int):
                    problems.append(f"{prefix}: non-integer begin/end")
                    continue
                if sub_begin != cursor or not begin <= sub_begin < sub_end <= end:
                    problems.append(
                        f"{prefix}: segments must be contiguous within parent [{begin}, {end})"
                    )
                if item.get("text") is not None and text[sub_begin:sub_end] != item.get("text"):
                    problems.append(f"{prefix}: text mismatch")
                if not str(item.get("category", "")).strip():
                    problems.append(f"{prefix}: missing category")
                cursor = sub_end
            if cursor != end:
                problems.append(f"span[{i}].subannotations: incomplete parent-span coverage")
    return problems


def check_labels(record: dict[str, Any], *, strict_taxonomy: bool = False) -> list[str]:
    """Verify label/category/subtype agreement (and taxonomy membership if strict)."""
    problems: list[str] = []
    for i, span in enumerate(record.get("spans", []) or []):
        if not isinstance(span, dict):
            continue
        label = span.get("label")
        category = span.get("category")
        subtype = span.get("subtype")
        if label is None and category is None:
            problems.append(f"span[{i}]: missing both label and category")
            continue
        if label is not None:
            cat, sub = split_label(str(label))
            if category is not None and category != cat:
                problems.append(f"span[{i}]: category {category!r} != label prefix {cat!r}")
            if subtype not in (None, "") and subtype != sub:
                problems.append(f"span[{i}]: subtype {subtype!r} != label suffix {sub!r}")
            if strict_taxonomy and not is_valid_label(str(label)):
                problems.append(f"span[{i}]: label {label!r} not in canonical taxonomy")
        if strict_taxonomy and category is not None:
            if not is_valid_category_subtype(str(category), subtype or None):
                problems.append(
                    f"span[{i}]: ({category!r}, {subtype!r}) not a valid taxonomy pair"
                )
    return problems


def validate_record(record: dict[str, Any], *, strict_taxonomy: bool = False) -> list[str]:
    """All problems for one record. Empty list == valid."""
    problems: list[str] = []
    if "document_id" not in record:
        problems.append("missing document_id")
    for key in ("annotations", "entities", "deid_spans", "items"):
        if key in record:
            problems.append(f"non-canonical span container {key!r}; use 'spans'")
    if "subannotations" in record:
        problems.append("top-level subannotations are non-canonical; nest them in their parent span")
    problems += check_offsets(record)
    problems += check_labels(record, strict_taxonomy=strict_taxonomy)
    return problems


def is_valid(record: dict[str, Any], *, strict_taxonomy: bool = False) -> bool:
    """True if ``record`` has no validation problems."""
    return not validate_record(record, strict_taxonomy=strict_taxonomy)
