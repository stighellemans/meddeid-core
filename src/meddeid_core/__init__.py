"""MedDeID's canonical document/span/metadata contract.

Pure-python core (always importable, no deps):
    taxonomy   — the 15-label data set and ordered 14-label model-head set
    normalize  — supported input-field canonicalization
    validate   — offset + label integrity checks

Typed layer (requires pydantic>=2):
    models     — Span, Patient, Caregiver, DocumentMetadata, Document
"""

from __future__ import annotations

from . import age_policy, artifacts, language, normalize, onboarding, taxonomy, validate
from .age_policy import (
    AGE_POLICY_SCHEMA_VERSION,
    AgeGranularityPolicy,
    AgePart,
    AgePolicyIdentity,
    load_age_granularity_policy,
)
from .language import DateReplacement, LanguageProfile
from .onboarding import (
    ATTEMPT_RECORD_CONTRACT,
    BATCH_MANIFEST_CONTRACT,
    GENERATION_TARGET_CONTRACT,
    PROFILE_REF_CONTRACT,
    REVIEW_DECISION_CONTRACT,
    AttemptRecord,
    BatchManifest,
    GenerationTarget,
    ProfileRef,
    ReviewDecision,
)
from .artifacts import (
    ARTIFACT_MANIFEST_VERSION,
    OFFSET_UNIT,
    SCHEMA_VERSION,
    attach_span_ids,
    build_artifact_manifest,
    stable_document_id,
    stable_span_id,
    validate_document_set,
)
from .normalize import normalize as normalize_obj
from .normalize import (
    normalize_metadata,
    normalize_name,
    normalize_record,
    normalize_span,
    normalize_subannotation,
)
from .taxonomy import (
    BERT_ENTITY_LABELS,
    CATEGORIES,
    ENTITY_LABELS,
    SUBTYPES,
    SUBTYPES_BY_CATEGORY,
    compose_label,
    is_valid_label,
    split_label,
)
from .validate import is_valid, validate_record

__all__ = [
    "taxonomy",
    "age_policy",
    "artifacts",
    "language",
    "onboarding",
    "LanguageProfile",
    "DateReplacement",
    "ProfileRef",
    "GenerationTarget",
    "AttemptRecord",
    "ReviewDecision",
    "BatchManifest",
    "PROFILE_REF_CONTRACT",
    "GENERATION_TARGET_CONTRACT",
    "ATTEMPT_RECORD_CONTRACT",
    "REVIEW_DECISION_CONTRACT",
    "BATCH_MANIFEST_CONTRACT",
    "AgePart",
    "AgePolicyIdentity",
    "AgeGranularityPolicy",
    "AGE_POLICY_SCHEMA_VERSION",
    "load_age_granularity_policy",
    "normalize",
    "validate",
    "normalize_obj",
    "normalize_record",
    "normalize_span",
    "normalize_subannotation",
    "normalize_metadata",
    "normalize_name",
    "validate_record",
    "is_valid",
    "SCHEMA_VERSION",
    "ARTIFACT_MANIFEST_VERSION",
    "OFFSET_UNIT",
    "stable_document_id",
    "stable_span_id",
    "attach_span_ids",
    "validate_document_set",
    "build_artifact_manifest",
    "ENTITY_LABELS",
    "BERT_ENTITY_LABELS",
    "CATEGORIES",
    "SUBTYPES",
    "SUBTYPES_BY_CATEGORY",
    "split_label",
    "compose_label",
    "is_valid_label",
]

# Typed models are optional (require pydantic).
try:  # pragma: no cover
    from . import models  # noqa: F401
    from .models import (  # noqa: F401
        Caregiver,
        Document,
        DocumentMetadata,
        KnownValue,
        Patient,
        Span,
        Subannotation,
    )

    __all__ += [
        "models",
        "Document",
        "Span",
        "Subannotation",
        "Patient",
        "Caregiver",
        "DocumentMetadata",
        "KnownValue",
    ]
except ImportError:  # pydantic not installed — core still works
    pass

__version__ = "0.2.0"
