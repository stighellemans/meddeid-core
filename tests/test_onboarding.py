from __future__ import annotations

import pytest

from meddeid_core import (
    BERT_ENTITY_LABELS,
    AttemptRecord,
    BatchManifest,
    GenerationTarget,
    ProfileRef,
    ReviewDecision,
)


def test_profile_ref_canonicalizes_unversioned_locale_identity() -> None:
    assert ProfileRef.parse("en_gb").identifier == "en-GB"
    assert ProfileRef.parse("nl_be").identifier == "nl-BE"
    with pytest.raises(ValueError, match="unversioned"):
        ProfileRef.parse("en-GB@1")
    with pytest.raises(ValueError, match="ambiguous"):
        ProfileRef.parse("en")


def test_generation_target_enforces_synthetic_label_contract() -> None:
    target = GenerationTarget(
        slot="patient.mrn",
        label="ID:Patient",
        semantic_type="patient_mrn",
    )
    assert target.to_dict()["label"] == "ID:Patient"
    with pytest.raises(ValueError, match="Anonymize_Other"):
        GenerationTarget(
            slot="misc",
            label="Anonymize_Other",
            semantic_type="other",
        )


def test_attempt_and_review_contracts_reject_untraceable_state() -> None:
    attempt = AttemptRecord(
        document_id="doc-1",
        attempt=1,
        role="author",
        outcome="accepted",
        estimated_cost_usd=0.01,
    )
    assert attempt.to_dict()["estimated_cost_usd"] == 0.01
    with pytest.raises(ValueError, match="one-based"):
        AttemptRecord(document_id="doc-1", attempt=0, role="author", outcome="failed")
    with pytest.raises(ValueError, match="unsupported review"):
        ReviewDecision(
            document_id="doc-1",
            document_sha256="abc",
            decision="pass",
            reviewer="reviewer",
            reviewed_at="2026-08-26T00:00:00Z",
        )


def test_batch_manifest_requires_exact_model_label_sequence() -> None:
    manifest = BatchManifest(
        batch_index=0,
        profiles=(ProfileRef.parse("en-GB"), ProfileRef.parse("en-US")),
        expected_documents=500,
        documents_sha256="documents",
        quality_report_sha256="quality",
    )
    assert manifest.to_dict()["allowed_labels"] == list(BERT_ENTITY_LABELS)
    assert manifest.to_dict()["forbidden_generated_labels"] == ["Anonymize_Other"]
    with pytest.raises(ValueError, match="BERT_ENTITY_LABELS"):
        BatchManifest(
            batch_index=0,
            profiles=(ProfileRef.parse("en-GB"),),
            expected_documents=1,
            documents_sha256="documents",
            quality_report_sha256="quality",
            allowed_labels=("Name:Patient",),
        )
