"""Canonical DEID label taxonomy (ProductionLabels v1.1).

Pure-python, no third-party deps, so this module can be imported anywhere
(conversion tools, training code, servers) without pulling in pydantic.

A ``label`` is either a bare ``category`` (e.g. ``"Date"``) or
``"Category:Subtype"`` (e.g. ``"Name:Patient"``). ``split_label`` /
``compose_label`` convert between the composite string and its parts.

Two label sets exist on purpose:

* ``ENTITY_LABELS`` (15) — the canonical set for data / annotation / eval / LLM
  output. Includes ``Anonymize_Other`` (interoperability catch-all + LLM gap
  flag).
* ``BERT_ENTITY_LABELS`` (14) — the token-classifier head subset: the 15
  minus ``Anonymize_Other`` (which the in-house BERT models do not predict).

Every model bundle MUST use the same ordered label list, or the id<->label
map breaks when switching models. Use these tuples as the single source of
that order.
"""

from __future__ import annotations

CONTRACT_VERSION = 1
TAXONOMY_VERSION = "ProductionLabels-v1.1"

# --- categories & subtypes -------------------------------------------------

CATEGORIES: tuple[str, ...] = (
    "Name",
    "Address_Location",
    "Organization",
    "ID",
    "Age_Birthdate",
    "Contactdetails",
    "Date",
    "Profession",
    "Anonymize_Other",
)

SUBTYPES: tuple[str, ...] = ("Patient", "Caregiver", "Other", "Healthcare")

# Which subtypes are valid for each category. Empty tuple => no subtype.
SUBTYPES_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "Name": ("Patient", "Caregiver", "Other"),
    "Address_Location": ("Patient", "Caregiver", "Other"),
    "Organization": ("Healthcare", "Other"),
    "ID": ("Patient", "Caregiver"),
    "Age_Birthdate": (),
    "Contactdetails": (),
    "Date": (),
    "Profession": (),
    "Anonymize_Other": (),
}

# --- canonical label lists (ORDER IS THE CONTRACT) -------------------------

#: Full 15-label set for data / annotation / eval / LLM output.
#:
#: ORDER IS ALPHABETICAL and load-bearing: trained token-classifier heads pin
#: their id<->label map to this order (see meddeid-training),
#: so ``BERT_ENTITY_LABELS`` below must equal that list exactly for checkpoints
#: to stay interchangeable. Do not reorder.
ENTITY_LABELS: tuple[str, ...] = (
    "Address_Location:Caregiver",
    "Address_Location:Other",
    "Address_Location:Patient",
    "Age_Birthdate",
    "Anonymize_Other",
    "Contactdetails",
    "Date",
    "ID:Caregiver",
    "ID:Patient",
    "Name:Caregiver",
    "Name:Other",
    "Name:Patient",
    "Organization:Healthcare",
    "Organization:Other",
    "Profession",
)

#: Token-classifier head subset (15 minus Anonymize_Other).
BERT_ENTITY_LABELS: tuple[str, ...] = tuple(
    lbl for lbl in ENTITY_LABELS if lbl != "Anonymize_Other"
)

#: LLMs emit the full set.
LLM_ENTITY_LABELS: tuple[str, ...] = ENTITY_LABELS

_LABEL_SET = frozenset(ENTITY_LABELS)


# --- helpers ---------------------------------------------------------------

def split_label(label: str) -> tuple[str, str | None]:
    """``"Name:Patient" -> ("Name", "Patient")``; ``"Date" -> ("Date", None)``."""
    category, sep, subtype = label.partition(":")
    return category, (subtype if sep else None)


def compose_label(category: str, subtype: str | None) -> str:
    """Inverse of :func:`split_label`. ``subtype`` of ``None``/``""`` => bare category."""
    return f"{category}:{subtype}" if subtype else category


def is_valid_label(label: str) -> bool:
    """True if ``label`` is one of the 15 canonical labels."""
    return label in _LABEL_SET


def is_valid_category_subtype(category: str, subtype: str | None) -> bool:
    """True if the (category, subtype) pair is allowed by the taxonomy.

    A bare label (no subtype) is only valid for categories that take no
    subtype (Date, Age_Birthdate, Contactdetails, Profession, Anonymize_Other).
    Categories that take subtypes (Name, Address_Location, Organization, ID)
    require one.
    """
    if category not in SUBTYPES_BY_CATEGORY:
        return False
    allowed = SUBTYPES_BY_CATEGORY[category]
    if subtype in (None, ""):
        return allowed == ()
    return subtype in allowed


def label_to_id(labels: tuple[str, ...] = ENTITY_LABELS) -> dict[str, int]:
    """Ordered label -> id map. Pass ``BERT_ENTITY_LABELS`` for the model head."""
    return {label: i for i, label in enumerate(labels)}


def id_to_label(labels: tuple[str, ...] = ENTITY_LABELS) -> dict[int, str]:
    """Ordered id -> label map."""
    return dict(enumerate(labels))


def bio_labels() -> tuple[str, ...]:
    """Binary BIO head labels."""
    return ("O", "B", "I")


def typed_bio_labels(entity_labels: tuple[str, ...] = BERT_ENTITY_LABELS) -> tuple[str, ...]:
    """Typed BIO head: ``O`` + ``B-<ent>``/``I-<ent>`` per entity, in canonical order."""
    out: list[str] = ["O"]
    for ent in entity_labels:
        out.append(f"B-{ent}")
        out.append(f"I-{ent}")
    return tuple(out)
