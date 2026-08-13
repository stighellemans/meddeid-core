from meddeid_core import taxonomy as tx
from meddeid_core.export_contracts import taxonomy_contract
import json
from pathlib import Path


def test_fifteen_entity_labels_including_anonymize_other():
    assert len(tx.ENTITY_LABELS) == 15
    assert "Anonymize_Other" in tx.ENTITY_LABELS


def test_bert_subset_is_fourteen_without_anonymize():
    assert len(tx.BERT_ENTITY_LABELS) == 14
    assert "Anonymize_Other" not in tx.BERT_ENTITY_LABELS


def test_split_and_compose_round_trip():
    for label in tx.ENTITY_LABELS:
        cat, sub = tx.split_label(label)
        assert tx.compose_label(cat, sub) == label


def test_bare_category_has_no_subtype():
    assert tx.split_label("Date") == ("Date", None)
    assert tx.compose_label("Date", None) == "Date"


def test_taxonomy_validity():
    assert tx.is_valid_label("Name:Patient")
    assert tx.is_valid_label("Date")
    assert not tx.is_valid_label("Name")  # Name requires a subtype
    assert tx.is_valid_category_subtype("Name", "Patient")
    assert tx.is_valid_category_subtype("Date", None)
    assert not tx.is_valid_category_subtype("Date", "Patient")
    assert not tx.is_valid_category_subtype("Name", None)


def test_bert_labels_match_deployed_alphabetical_order():
    # ORDER IS THE CONTRACT: must equal meddeid CANONICAL_ENTITY_TYPES exactly,
    # or trained checkpoints' id<->label maps break. This tuple is the regression
    # guard against re-adding a removed label.
    assert tx.BERT_ENTITY_LABELS == (
        "Address_Location:Caregiver", "Address_Location:Other", "Address_Location:Patient",
        "Age_Birthdate", "Contactdetails", "Date", "ID:Caregiver", "ID:Patient",
        "Name:Caregiver", "Name:Other", "Name:Patient", "Organization:Healthcare",
        "Organization:Other", "Profession",
    )


def test_label_id_maps_are_ordered_and_stable():
    m = tx.label_to_id(tx.BERT_ENTITY_LABELS)
    assert m["Address_Location:Caregiver"] == 0
    assert len(m) == 14
    assert tx.id_to_label(tx.BERT_ENTITY_LABELS)[0] == "Address_Location:Caregiver"


def test_typed_bio_labels():
    typed = tx.typed_bio_labels(tx.BERT_ENTITY_LABELS)
    assert typed[0] == "O"
    assert "B-Name:Patient" in typed and "I-Name:Patient" in typed
    assert len(typed) == 1 + 2 * 14


def test_exported_contract_is_derived_from_taxonomy():
    contract = taxonomy_contract()
    assert contract["entity_labels"] == list(tx.ENTITY_LABELS)
    assert contract["model_entity_labels"] == list(tx.BERT_ENTITY_LABELS)
    assert contract["subtypes_by_category"]["Organization"] == ["Healthcare", "Other"]


def test_committed_contract_is_current():
    contract_path = Path(__file__).resolve().parents[1] / "contracts" / "taxonomy.json"
    assert json.loads(contract_path.read_text(encoding="utf-8")) == taxonomy_contract()
