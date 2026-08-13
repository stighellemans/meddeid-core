from meddeid_core.validate import check_offsets, is_valid, validate_record


CANONICAL = {
    "document_id": "d1",
    "text": "Jan Peeters komt terug.",
    "spans": [
        {"begin": 0, "end": 11, "text": "Jan Peeters", "label": "Name:Patient",
         "category": "Name", "subtype": "Patient"},
    ],
}


def test_valid_record_passes():
    assert is_valid(CANONICAL, strict_taxonomy=True)
    assert validate_record(CANONICAL) == []


def test_offset_text_mismatch_is_caught():
    bad = {"document_id": "d", "text": "Jan Peeters", "spans": [
        {"begin": 0, "end": 3, "text": "Jon", "label": "Name:Patient"}]}
    problems = check_offsets(bad)
    assert problems and "text mismatch" in problems[0]


def test_out_of_range_offsets_caught():
    bad = {"document_id": "d", "text": "abc", "spans": [
        {"begin": 0, "end": 99, "text": "abc", "label": "Date"}]}
    assert any("out of range" in p for p in check_offsets(bad))


def test_label_category_disagreement_caught():
    bad = {"document_id": "d", "text": "abc", "spans": [
        {"begin": 0, "end": 3, "text": "abc", "label": "Name:Patient", "category": "Date"}]}
    problems = validate_record(bad)
    assert any("category" in p for p in problems)


def test_missing_document_id_caught():
    assert any("document_id" in p for p in validate_record({"text": "x", "spans": []}))


def test_reid_record_without_text_is_tolerated():
    # re-identification-ui records have no text; offset check should no-op
    rec = {"document_id": "d", "spans": [{"begin": 0, "end": 3, "label": "Date", "text": "abc"}]}
    assert check_offsets(rec) == []


def test_nested_subannotations_must_partition_parent_span():
    valid = {
        "document_id": "d",
        "text": "Jan Peeters",
        "spans": [{
            "begin": 0,
            "end": 11,
            "text": "Jan Peeters",
            "label": "Name:Patient",
            "subannotations": [
                {"begin": 0, "end": 3, "text": "Jan", "category": "given"},
                {"begin": 3, "end": 4, "text": " ", "category": "formatting"},
                {"begin": 4, "end": 11, "text": "Peeters", "category": "family"},
            ],
        }],
    }
    assert validate_record(valid) == []

    invalid = {**valid, "subannotations": valid["spans"][0]["subannotations"]}
    assert any("top-level subannotations" in problem for problem in validate_record(invalid))
