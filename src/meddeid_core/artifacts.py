"""Stable identities and manifests for canonical MedDeID JSONL artifacts.

The suite passes documents through several independently versioned tools.  File
names and row positions are deliberately *not* identities: a document keeps its
``document_id`` and a primary span keeps its ``span_id`` when files are renamed,
sorted, merged, or copied between machines.

All canonical character offsets are zero-based, half-open Unicode code-point
offsets.  Python string indexes already use that unit.  JavaScript clients must
convert at their DOM boundary because DOM selection indexes are UTF-16 code
units.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "meddeid.schema.v1"
ARTIFACT_MANIFEST_VERSION = "meddeid.artifact-manifest.v1"
OFFSET_UNIT = "unicode_codepoints"


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes used by all identity hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_document_id(
    source_namespace: str,
    source_record_id: str,
    *,
    secret: str | bytes | None = None,
) -> str:
    """Create a non-reversible, stable ID without exposing a hospital record ID.

    Supplying a hospital-held ``secret`` uses HMAC and prevents dictionary
    attacks against predictable source identifiers.  The unkeyed form remains
    useful for synthetic/public data but should not be used for patient data.
    """

    namespace = source_namespace.strip()
    record_id = source_record_id.strip()
    if not namespace or not record_id:
        raise ValueError("source_namespace and source_record_id must be non-empty")
    payload = canonical_json_bytes([namespace, record_id])
    if secret is None:
        digest = hashlib.sha256(payload).hexdigest()
    else:
        key = secret.encode("utf-8") if isinstance(secret, str) else secret
        if not key:
            raise ValueError("secret must be non-empty when supplied")
        digest = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return f"doc-{digest[:24]}"


def stable_span_id(document_id: str, begin: int, end: int, label: str) -> str:
    """Identity for a primary span, independent of its position in a list."""

    if not document_id.strip() or not label.strip():
        raise ValueError("document_id and label must be non-empty")
    if not isinstance(begin, int) or not isinstance(end, int) or begin < 0 or end <= begin:
        raise ValueError("span offsets must satisfy 0 <= begin < end")
    digest = sha256_bytes(canonical_json_bytes([document_id, begin, end, label]))
    return f"span-{digest[:24]}"


def attach_span_ids(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with a stable ``span_id`` on every canonical primary span."""

    document_id = str(record.get("document_id", ""))
    result = dict(record)
    result["spans"] = []
    for raw_span in record.get("spans", []) or []:
        span = dict(raw_span)
        expected = stable_span_id(
            document_id,
            int(span["begin"]),
            int(span["end"]),
            str(span["label"]),
        )
        if span.get("span_id") not in (None, expected):
            raise ValueError(
                f"{document_id}: span_id {span['span_id']!r} does not match canonical identity {expected!r}"
            )
        span["span_id"] = expected
        result["spans"].append(span)
    return result


def validate_document_set(records: Sequence[Mapping[str, Any]]) -> None:
    """Reject missing/duplicate IDs and conflicting repeated document text."""

    seen: dict[str, str] = {}
    for index, record in enumerate(records):
        document_id = record.get("document_id")
        text = record.get("text")
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError(f"row {index + 1}: document_id must be a non-empty string")
        if not isinstance(text, str):
            raise ValueError(f"{document_id}: text must be a string")
        text_hash = sha256_bytes(text.encode("utf-8"))
        if document_id in seen:
            detail = "with different text" if seen[document_id] != text_hash else ""
            raise ValueError(f"duplicate document_id {document_id!r} {detail}".rstrip())
        seen[document_id] = text_hash


def build_artifact_manifest(
    *,
    role: str,
    artifact_path: str | Path,
    records: Sequence[Mapping[str, Any]],
    producer: Mapping[str, str],
    parents: Iterable[Mapping[str, str]] = (),
    contracts: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a checksummed, lineage-aware manifest for one canonical JSONL file."""

    if not role.strip():
        raise ValueError("artifact role must be non-empty")
    validate_document_set(records)
    path = Path(artifact_path)
    spans = sum(len(record.get("spans", []) or []) for record in records)
    return {
        "manifest_version": ARTIFACT_MANIFEST_VERSION,
        "artifact": {
            "role": role,
            "filename": path.name,
            "sha256": sha256_file(path),
        },
        "contracts": {
            "schema_version": SCHEMA_VERSION,
            "offset_unit": OFFSET_UNIT,
            **dict(contracts or {}),
        },
        "producer": dict(producer),
        "parents": [dict(parent) for parent in parents],
        "counts": {"documents": len(records), "spans": spans},
    }

