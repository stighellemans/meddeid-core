import json

import pytest

from meddeid_core.artifacts import (
    OFFSET_UNIT,
    attach_span_ids,
    build_artifact_manifest,
    stable_document_id,
    stable_span_id,
    validate_document_set,
)


def test_stable_ids_do_not_depend_on_filename_or_span_order():
    assert stable_document_id("hospital-a", "patient-42", secret="local key") == stable_document_id(
        "hospital-a", "patient-42", secret="local key"
    )
    assert stable_document_id("hospital-a", "patient-42", secret="other key") != stable_document_id(
        "hospital-a", "patient-42", secret="local key"
    )
    assert stable_span_id("doc-1", 2, 5, "Name:Patient").startswith("span-")


def test_attach_span_ids_rejects_stale_identity():
    record = {
        "document_id": "doc-1",
        "text": "😀Jan",
        "spans": [{"begin": 1, "end": 4, "text": "Jan", "label": "Name:Patient"}],
    }
    result = attach_span_ids(record)
    assert result["spans"][0]["span_id"] == stable_span_id("doc-1", 1, 4, "Name:Patient")
    record["spans"][0]["span_id"] = "span-stale"
    with pytest.raises(ValueError, match="does not match canonical identity"):
        attach_span_ids(record)


def test_document_set_rejects_duplicate_ids():
    rows = [
        {"document_id": "same", "text": "first", "spans": []},
        {"document_id": "same", "text": "second", "spans": []},
    ]
    with pytest.raises(ValueError, match="duplicate document_id"):
        validate_document_set(rows)


def test_manifest_records_hash_lineage_and_unicode_offset_contract(tmp_path):
    rows = [{"document_id": "doc-1", "text": "😀Jan", "spans": []}]
    artifact = tmp_path / "annotations.jsonl"
    artifact.write_text(json.dumps(rows[0], ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = build_artifact_manifest(
        role="primary_annotations",
        artifact_path=artifact,
        records=rows,
        producer={"name": "meddeid-annotate", "version": "0.1.0"},
        parents=[{"role": "input_documents", "sha256": "a" * 64}],
    )
    assert manifest["contracts"]["offset_unit"] == OFFSET_UNIT == "unicode_codepoints"
    assert manifest["artifact"]["sha256"] and manifest["counts"] == {"documents": 1, "spans": 0}
    assert manifest["parents"][0]["role"] == "input_documents"
