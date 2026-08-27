"""Language, corpus, review, and model-onboarding contracts.

These small dependency-free values are shared by contributor tooling.  They do
not replace the canonical document schema; they describe the provenance and
state around producing canonical documents.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from .taxonomy import BERT_ENTITY_LABELS


PROFILE_REF_CONTRACT = "meddeid.profile-ref.v1"
GENERATION_TARGET_CONTRACT = "meddeid.generation-target.v1"
ATTEMPT_RECORD_CONTRACT = "meddeid.production-attempt.v1"
REVIEW_DECISION_CONTRACT = "meddeid.review-decision.v1"
BATCH_MANIFEST_CONTRACT = "meddeid.production-batch.v1"


def _canonical_selection(value: str) -> str:
    parts = value.strip().replace("_", "-").split("-")
    if not parts or not parts[0]:
        raise ValueError("profile selection must be non-empty")
    canonical = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 2 and part.isalpha():
            canonical.append(part.upper())
        elif len(part) == 4 and part.isalpha():
            canonical.append(part.title())
        else:
            canonical.append(part)
    selection = "-".join(canonical)
    if selection.lower() == "en":
        raise ValueError(
            "bare 'en' is ambiguous; select a regional profile such as en-GB or en-US"
        )
    return selection


@dataclass(frozen=True)
class ProfileRef:
    """Canonical, unversioned locale identity such as ``en-GB``."""

    selection: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "selection", _canonical_selection(self.selection))

    @classmethod
    def parse(cls, value: str) -> "ProfileRef":
        raw = str(value).strip()
        if "@" in raw:
            raise ValueError(
                "language profiles are unversioned locale identifiers; "
                f"use {raw.split('@', 1)[0]!r}; package releases, resource manifests, "
                "model bundles, and Git history provide provenance"
            )
        return cls(raw)

    @property
    def identifier(self) -> str:
        return self.selection

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": PROFILE_REF_CONTRACT,
            "selection": self.selection,
        }


@dataclass(frozen=True)
class GenerationTarget:
    """One private rendering slot mapped onto the stable public taxonomy."""

    slot: str
    label: str
    semantic_type: str
    value: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.slot.strip():
            raise ValueError("generation target slot must be non-empty")
        if self.label == "Anonymize_Other":
            raise ValueError("synthetic generation must not use Anonymize_Other")
        if self.label not in BERT_ENTITY_LABELS:
            raise ValueError(
                f"generated label {self.label!r} is outside BERT_ENTITY_LABELS"
            )
        if not self.semantic_type.strip():
            raise ValueError("generation target semantic_type must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": GENERATION_TARGET_CONTRACT,
            **asdict(self),
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True)
class AttemptRecord:
    """Append-only accounting record for one author or reviewer request."""

    document_id: str
    attempt: int
    role: str
    outcome: str
    model: str | None = None
    response_id: str | None = None
    prompt_contract_version: str | None = None
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    estimated_cost_usd: float = 0.0
    created_at: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("attempt document_id must be non-empty")
        if self.attempt < 1:
            raise ValueError("attempt number must be one-based")
        if self.role not in {"author", "reviewer", "local"}:
            raise ValueError(f"unsupported attempt role: {self.role!r}")
        for name in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_tokens",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": ATTEMPT_RECORD_CONTRACT,
            **asdict(self),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ReviewDecision:
    """Content-bound personal decision for one document revision."""

    document_id: str
    document_sha256: str
    decision: str
    reviewer: str
    reviewed_at: str
    notes: str = ""
    replacement_document_id: str | None = None

    def __post_init__(self) -> None:
        if self.decision not in {"accept", "edit", "regenerate", "reject"}:
            raise ValueError(f"unsupported review decision: {self.decision!r}")
        if not self.document_id.strip() or not self.document_sha256.strip():
            raise ValueError(
                "review decision must identify the document and content hash"
            )
        if not self.reviewer.strip() or not self.reviewed_at.strip():
            raise ValueError("review decision must identify reviewer and timestamp")

    def to_dict(self) -> dict[str, Any]:
        return {"contract_version": REVIEW_DECISION_CONTRACT, **asdict(self)}


@dataclass(frozen=True)
class BatchManifest:
    """Minimal language-neutral batch identity used by the production runner."""

    batch_index: int
    profiles: tuple[ProfileRef, ...]
    expected_documents: int
    documents_sha256: str
    quality_report_sha256: str
    allowed_labels: tuple[str, ...] = tuple(BERT_ENTITY_LABELS)
    forbidden_generated_labels: tuple[str, ...] = ("Anonymize_Other",)
    independently_authored: bool = True
    signoff_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.batch_index < 0:
            raise ValueError("batch_index must be non-negative")
        if not self.profiles:
            raise ValueError("batch manifest requires at least one profile")
        if self.expected_documents < 1:
            raise ValueError("expected_documents must be positive")
        if tuple(self.allowed_labels) != tuple(BERT_ENTITY_LABELS):
            raise ValueError("synthetic batch labels must equal BERT_ENTITY_LABELS")
        if tuple(self.forbidden_generated_labels) != ("Anonymize_Other",):
            raise ValueError("synthetic batches must forbid Anonymize_Other")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": BATCH_MANIFEST_CONTRACT,
            "batch_index": self.batch_index,
            "profiles": [profile.to_dict() for profile in self.profiles],
            "expected_documents": self.expected_documents,
            "documents_sha256": self.documents_sha256,
            "quality_report_sha256": self.quality_report_sha256,
            "allowed_labels": list(self.allowed_labels),
            "forbidden_generated_labels": list(self.forbidden_generated_labels),
            "independently_authored": self.independently_authored,
            "signoff_sha256": self.signoff_sha256,
        }


__all__ = [
    "ATTEMPT_RECORD_CONTRACT",
    "BATCH_MANIFEST_CONTRACT",
    "GENERATION_TARGET_CONTRACT",
    "PROFILE_REF_CONTRACT",
    "REVIEW_DECISION_CONTRACT",
    "AttemptRecord",
    "BatchManifest",
    "GenerationTarget",
    "ProfileRef",
    "ReviewDecision",
]
