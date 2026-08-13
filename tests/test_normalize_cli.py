import json

import pytest

from meddeid_core.normalize_cli import normalize_jsonl_text


def test_normalize_jsonl_text_normalizes_spans():
    source = json.dumps({
        "doc_id": "doc-1",
        "plain_text": "Jan",
        "spans": [{
            "start": 0,
            "end": 3,
            "Category": "Name",
            "Subtype": "Patient",
        }],
    })

    row = json.loads(normalize_jsonl_text(source))

    assert row["document_id"] == "doc-1"
    assert row["text"] == "Jan"
    assert row["spans"][0]["begin"] == 0
    assert row["spans"][0]["label"] == "Name:Patient"
    assert "doc_id" not in row
    assert "Category" not in row["spans"][0]


def test_normalize_jsonl_text_rejects_noncanonical_annotations_container():
    source = json.dumps({"document_id": "doc-1", "text": "Jan", "annotations": []})
    with pytest.raises(ValueError, match="canonical key 'spans'"):
        normalize_jsonl_text(source)


def test_normalize_jsonl_text_reports_line_number():
    with pytest.raises(ValueError, match="line 2"):
        normalize_jsonl_text('{}\nnot-json\n', source="legacy.jsonl")
