import pytest

pytest.importorskip("pydantic")

from meddeid_core.models import (  # noqa: E402
    Document,
    DocumentMetadata,
    KnownValue,
    Span,
)


def test_span_fills_category_subtype_from_label():
    s = Span(begin=0, end=3, text="abc", label="Name:Patient")
    assert s.category == "Name" and s.subtype == "Patient"


def test_span_bare_label_has_no_subtype():
    s = Span(begin=0, end=3, text="abc", label="Date")
    assert s.category == "Date" and s.subtype is None


def test_span_inconsistent_label_rejected():
    with pytest.raises(ValueError):
        Span(begin=0, end=3, text="abc", label="Name:Patient", category="Date")


def test_span_allows_extras():
    s = Span(begin=0, end=3, text="abc", label="Date", score=0.9, replacement="[Date]")
    assert s.model_dump()["score"] == 0.9


def test_span_owns_complete_absolute_offset_subannotations():
    span = Span(
        begin=10,
        end=21,
        text="Jan Peeters",
        label="Name:Patient",
        subannotations=[
            {"begin": 10, "end": 13, "text": "Jan", "category": "given"},
            {"begin": 13, "end": 14, "text": " ", "category": "formatting"},
            {"begin": 14, "end": 21, "text": "Peeters", "category": "family"},
        ],
    )
    assert [item.category for item in span.subannotations] == ["given", "formatting", "family"]


def test_span_rejects_incomplete_subannotation_partition():
    with pytest.raises(ValueError, match="contiguous partition"):
        Span(
            begin=0,
            end=3,
            text="Jan",
            label="Name:Patient",
            subannotations=[
                {"begin": 1, "end": 3, "text": "an", "category": "given"},
            ],
        )


def test_known_value_accepts_valid_label():
    kv = KnownValue(value="83.10.15-123.45", label="ID:Patient")
    assert kv.value == "83.10.15-123.45" and kv.label == "ID:Patient"


def test_known_value_rejects_invalid_label():
    with pytest.raises(ValueError):
        KnownValue(value="123", label="SSN")  # not a taxonomy label
    with pytest.raises(ValueError):
        KnownValue(value="123", label="Organization:Patient")  # retired label


def test_known_value_rejects_empty_value():
    with pytest.raises(ValueError):
        KnownValue(value="   ", label="ID:Patient")


def test_known_value_label_enum_advertised_in_schema():
    enum = KnownValue.model_json_schema()["properties"]["label"]["enum"]
    assert "ID:Patient" in enum and "Name:Other" in enum and len(enum) == 15


def test_metadata_known_values_parsed():
    meta = DocumentMetadata.model_validate(
        {"known_values": [{"value": "jan@vb.be", "label": "Contactdetails"}]}
    )
    assert meta.known_values[0].label == "Contactdetails"


@pytest.mark.parametrize("retired_key", ["patient_name", "caregiver_names"])
def test_metadata_model_rejects_retired_identity_keys(retired_key):
    with pytest.raises(ValueError, match="retired metadata key"):
        DocumentMetadata.model_validate({retired_key: {}})


def test_document_from_raw_normalizes_variant():
    raw = {
        "doc_id": "note-1",
        "text": "Jan Peeters",
        "spans": [{"start": 0, "end": 11, "tag": "Name:Patient", "text": "Jan Peeters"}],
        "metadata": {"language": "nl", "patient": {"first_name": "Jan", "last_name": "Peeters"}},
        "annotated": True,
    }
    doc = Document.from_raw(raw)
    assert doc.document_id == "note-1"
    assert doc.spans[0].category == "Name" and doc.spans[0].subtype == "Patient"
    assert doc.metadata.lang == "nl"
    assert doc.metadata.patient.given_name == "Jan"


def test_document_model_rejects_annotations_container():
    with pytest.raises(ValueError, match="canonical key 'spans'"):
        Document.model_validate({"document_id": "d1", "text": "Jan", "annotations": []})
