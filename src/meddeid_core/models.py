"""Canonical DEID Pydantic models (v2).

Importing this module requires ``pydantic>=2``. The pure-python core
(``taxonomy``, ``normalize``, ``validate``) does **not**, so conversion tools
can run without it.

The canonical field names are the contract; unknown extras are allowed on
every model (``extra="allow"``) per the "extras allowed" rule. Use
``Document.from_raw(...)`` to normalize any variant record and validate it in
one step.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .normalize import normalize_record
from .taxonomy import ENTITY_LABELS, compose_label, is_valid_label, split_label


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class Subannotation(_Base):
    """A reviewed semantic segment inside one primary gold span.

    Offsets remain absolute document offsets. Nesting records ownership while
    absolute offsets keep evaluation and text-integrity checks straightforward.
    """

    begin: int = Field(description="Inclusive document character offset.")
    end: int = Field(description="Exclusive document character offset.")
    text: str = Field(description="Original text covered by the segment.")
    category: str = Field(description="Benchmark subannotation category.")


class Span(_Base):
    begin: int = Field(description="Inclusive character offset.")
    end: int = Field(description="Exclusive character offset.")
    text: str = Field(description="Original text covered by the span (== source[begin:end]).")
    label: str = Field(description="Full label: 'Category' or 'Category:Subtype'.")
    category: str | None = Field(default=None, description="Top-level category.")
    subtype: str | None = Field(default=None, description="Subtype, or null.")
    replacement: str | None = Field(
        default=None,
        description="Exact bracketed text used when rendering this inference span.",
    )
    subannotations: list[Subannotation] = Field(
        default_factory=list,
        description="Confirmed benchmark segments owned by this primary span.",
    )
    # extras allowed: score, replacement, confirmed, native_label, ...

    @model_validator(mode="after")
    def _fill_and_check(self) -> "Span":
        cat, sub = split_label(self.label)
        if self.category is None:
            self.category = cat
        if self.subtype is None:
            self.subtype = sub
        if self.end < self.begin:
            raise ValueError(f"end ({self.end}) < begin ({self.begin})")
        if compose_label(self.category, self.subtype) != self.label:
            raise ValueError(
                f"label {self.label!r} inconsistent with category/subtype "
                f"({self.category!r}, {self.subtype!r})"
            )
        if self.subannotations:
            cursor = self.begin
            for index, item in enumerate(self.subannotations):
                if item.begin != cursor or not item.begin < item.end <= self.end:
                    raise ValueError(
                        f"subannotations[{index}] must form a contiguous partition "
                        f"of span [{self.begin}, {self.end})"
                    )
                relative_begin = item.begin - self.begin
                relative_end = item.end - self.begin
                if self.text[relative_begin:relative_end] != item.text:
                    raise ValueError(f"subannotations[{index}] text does not match parent span")
                cursor = item.end
            if cursor != self.end:
                raise ValueError("subannotations must cover the complete parent span")
        return self


class Patient(_Base):
    given_name: str | None = None
    family_name: str | None = None
    birth_date: str | None = Field(
        default=None,
        description="Trusted full birth date used for locale-aware span recovery.",
    )


class Caregiver(_Base):
    given_name: str | None = None
    family_name: str | None = None


class KnownValue(_Base):
    """A caller-asserted value to locate and tag in the text.

    Unlike a :class:`Span`, a known value carries no offsets — post-processing
    resolves them (separator-tolerant, so ``"0470 12 34 56"`` matches
    ``"0470123456"``). ``label`` must be one of the canonical taxonomy labels;
    this is the single enforcement point for the request-side contract, so the
    mechanical injector in ``post-process`` can trust the label.
    """

    value: str = Field(
        description="Literal string to locate and tag (e.g. an RRN, RIZIV nr, email, name).",
        examples=["83.10.15-123.45"],
    )
    label: str = Field(
        description="Canonical taxonomy label to assign to every match of ``value``.",
        examples=["ID:Patient"],
        json_schema_extra={"enum": list(ENTITY_LABELS)},
    )

    @model_validator(mode="after")
    def _check(self) -> "KnownValue":
        if not self.value.strip():
            raise ValueError("known value 'value' must be a non-empty string")
        if not is_valid_label(self.label):
            raise ValueError(
                f"known value label {self.label!r} is not a valid taxonomy label; "
                f"expected one of {list(ENTITY_LABELS)}"
            )
        return self


class DocumentMetadata(_Base):
    lang: str | None = None
    document_creation_date: str | None = Field(
        default=None,
        description="Reference date used to convert birthdates to generalized ages.",
    )
    date_shift_days: int | None = Field(
        default=None,
        description="Explicit date shift in days; omit or use zero for placeholders.",
    )
    patient: Patient | None = None
    caregivers: list[Caregiver] | None = None
    known_values: list[KnownValue] | None = Field(
        default=None,
        description=(
            "Caller-asserted values to locate and tag, e.g. "
            "[{'value': '83.10.15-123.45', 'label': 'ID:Patient'}]. Complements "
            "patient/caregivers (which do token-aware name recovery); "
            "use known_values for IDs, contact details, or any name whose exact "
            "string is known, tagged with any valid label."
        ),
    )
    # extras allowed: source, synthea_source, document_type, ...

    @model_validator(mode="before")
    @classmethod
    def _reject_retired_identity_keys(cls, value: Any) -> Any:
        if isinstance(value, dict):
            retired = [key for key in ("patient_name", "caregiver_names") if key in value]
            if retired:
                raise ValueError(
                    f"retired metadata key(s) {retired}; use 'patient' and 'caregivers'"
                )
        return value


class Document(_Base):
    document_id: str
    text: str | None = None
    spans: list[Span] = Field(default_factory=list)
    deid_text: str | None = None  # optional-where-it-exists (D6)
    metadata: DocumentMetadata | None = None
    warnings: list[dict[str, str]] = Field(default_factory=list)
    processing: dict[str, Any] = Field(default_factory=dict)
    # extras allowed: annotated, status, source_dataset, ...

    @model_validator(mode="before")
    @classmethod
    def _reject_noncanonical_span_containers(cls, value: Any) -> Any:
        if isinstance(value, dict):
            forbidden = [
                key for key in ("annotations", "entities", "deid_spans", "items") if key in value
            ]
            if forbidden:
                raise ValueError(
                    f"non-canonical span container(s) {forbidden}; use the one canonical key 'spans'"
                )
            if "subannotations" in value:
                raise ValueError(
                    "top-level subannotations are non-canonical; nest them in their parent span"
                )
        return value

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "Document":
        """Normalize any variant record, then validate into a Document."""
        return cls.model_validate(normalize_record(raw))
