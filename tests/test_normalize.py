"""Normalizer tests using REAL variant shapes observed across the workspace."""

import pytest

from meddeid_core.normalize import (
    normalize_metadata,
    normalize_name,
    normalize_record,
    normalize_span,
)


# --- spans -----------------------------------------------------------------

def test_deduce_docdeid_span():
    # docdeid Annotation: start_char/end_char/tag
    out = normalize_span({"start_char": 0, "end_char": 4, "tag": "patient", "text": "dr A"})
    assert out["begin"] == 0 and out["end"] == 4
    assert out["label"] == "patient" and out["category"] == "patient"


def test_synthetic_capitalized_category_subtype():
    out = normalize_span(
        {"begin": 34, "end": 44, "label": "Date", "text": "15-01-2026",
         "Category": "Date", "Subtype": None, "confirmed": True}
    )
    assert out["category"] == "Date" and out["subtype"] is None
    assert "Category" not in out and "Subtype" not in out
    assert out["confirmed"] is True  # extras preserved


def test_server_start_offset_and_derive_parts():
    out = normalize_span({"start": 19, "end": 30, "label": "Name:Patient", "text": "Jan Peeters"})
    assert out["begin"] == 19
    assert out["category"] == "Name" and out["subtype"] == "Patient"


def test_llm_confidence_to_score():
    out = normalize_span({"begin": 3, "end": 9, "label": "Date", "text": "vandaag", "confidence": 0.8})
    assert out["score"] == 0.8 and "confidence" not in out


def test_span_annotations_eval_char_offsets():
    out = normalize_span({"char_begin": 5, "char_end": 8, "label": "ID:Patient", "text": "123"})
    assert out["begin"] == 5 and out["end"] == 8


def test_span_idempotent():
    once = normalize_span({"start": 1, "end": 2, "label": "Name:Patient", "text": "X"})
    twice = normalize_span(once)
    assert once == twice


# --- names & metadata ------------------------------------------------------

def test_name_aliases():
    assert normalize_name({"first_name": "Jan", "last_name": "Peeters"}) == {
        "given_name": "Jan", "family_name": "Peeters"
    }


def test_name_deduce_first_names_list_and_surname():
    out = normalize_name({"first_names": ["Jan", "Willem"], "surname": "Peeters", "initials": "JW"})
    assert out["given_name"] == "Jan Willem" and out["family_name"] == "Peeters"
    assert "initials" not in out


def test_name_full_string_split():
    assert normalize_name("Noa-Lynn Dosin") == {"given_name": "Noa-Lynn", "family_name": "Dosin"}
    assert normalize_name("Dosin, Noa-Lynn") == {"given_name": "Noa-Lynn", "family_name": "Dosin"}


def test_metadata_language_and_flat_patient_fields():
    # legacy flat annotation metadata
    out = normalize_metadata(
        {"language": "nl", "patient_given_name": "Jan", "patient_last_name": "Peeters",
         "patient_birthdate": "1981-03-12", "text_creation_date": "2024-05-14"}
    )
    assert out["lang"] == "nl"
    assert out["patient"] == {"given_name": "Jan", "family_name": "Peeters", "birth_date": "1981-03-12"}
    assert out["document_creation_date"] == "2024-05-14"


def test_metadata_caregivers_full_strings():
    out = normalize_metadata({"caregivers": ["Anke De Vos", "W Stevens"]})
    assert out["caregivers"][0] == {"given_name": "Anke De", "family_name": "Vos"}
    assert out["caregivers"][1] == {"given_name": "W", "family_name": "Stevens"}


def test_metadata_created_dt_tm_alias():
    out = normalize_metadata({"created_dt_tm": "07/05/2026", "name": "Jan Peeters", "birth_dt": "1981-03-12"})
    assert out["document_creation_date"] == "07/05/2026"
    assert out["patient"]["family_name"] == "Peeters"
    assert out["patient"]["birth_date"] == "1981-03-12"


@pytest.mark.parametrize("retired_key", ["patient_name", "caregiver_names"])
def test_metadata_rejects_retired_identity_keys(retired_key):
    with pytest.raises(ValueError, match="retired metadata key"):
        normalize_metadata({retired_key: {}})


def test_metadata_preserves_extras():
    out = normalize_metadata({"language": "nl", "synthea_source": {"id": 7}, "source": "ehr"})
    assert out["synthea_source"] == {"id": 7} and out["source"] == "ehr"


# --- records ---------------------------------------------------------------

def test_record_spans_and_doc_id():
    rec = {
        "doc_id": "note-1",
        "text": "Jan Peeters",
        "spans": [{"begin": 0, "end": 11, "label": "Name:Patient", "text": "Jan Peeters",
                   "Category": "Name", "Subtype": "Patient"}],
        "metadata": {"language": "nl"},
        "annotated": True,
    }
    out = normalize_record(rec)
    assert out["document_id"] == "note-1"
    assert "spans" in out
    assert out["spans"][0]["category"] == "Name" and out["spans"][0]["subtype"] == "Patient"
    assert out["metadata"]["lang"] == "nl"
    assert out["annotated"] is True  # extra preserved


@pytest.mark.parametrize("key", ["annotations", "entities", "deid_spans", "items"])
def test_record_rejects_noncanonical_span_containers(key):
    with pytest.raises(ValueError, match="use the one canonical key 'spans'"):
        normalize_record({"document_id": "d1", "text": "abc", key: []})


def test_record_already_canonical_is_idempotent():
    rec = {
        "document_id": "d1",
        "text": "Jan",
        "spans": [{"begin": 0, "end": 3, "text": "Jan", "label": "Name:Patient",
                   "category": "Name", "subtype": "Patient"}],
        "metadata": {"lang": "nl", "patient": {"given_name": "Jan", "family_name": "P"}},
    }
    once = normalize_record(rec)
    twice = normalize_record(once)
    assert once == twice
    assert once["spans"][0]["category"] == "Name"


def test_top_level_subannotations_are_rejected():
    rec = {
        "document_id": "d1",
        "text": "Jan Peeters",
        "spans": [
            {"begin": 0, "end": 11, "text": "Jan Peeters", "label": "Name:Patient"}
        ],
        "subannotations": [
            {"begin": 0, "end": 3, "text": "Jan", "category": "given"},
            {"begin": 3, "end": 4, "text": " ", "category": "formatting"},
            {"begin": 4, "end": 11, "text": "Peeters", "category": "family"},
        ],
    }
    with pytest.raises(ValueError, match="top-level subannotations"):
        normalize_record(rec)
