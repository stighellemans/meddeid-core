"""Canonicalization helpers for supported input-field variants.

Operates on plain dicts (no pydantic) so it can rewrite any JSON/JSONL/parquet
record in place. Every function is **idempotent**: feeding canonical data
through it is a no-op.

Typical use::

    from meddeid_core.normalize import normalize_record
    canonical = normalize_record(json.loads(line))
"""

from __future__ import annotations

from typing import Any

from .taxonomy import compose_label, split_label

# --- key aliases (first match wins, canonical key listed first) ------------

_ID_KEYS = ("document_id", "id", "doc_id", "note_id", "custom_id", "case_id", "record_id")
_TEXT_KEYS = ("text", "raw_text", "plain_text", "marked_text")
_DEID_TEXT_KEYS = ("deid_text", "deidentified_text", "output_text", "redacted")
_SPANS_KEYS = ("spans",)
_FORBIDDEN_SPAN_CONTAINER_KEYS = ("annotations", "entities", "deid_spans", "items")

_BEGIN_KEYS = ("begin", "start", "start_char", "char_begin", "start_offset")
_END_KEYS = ("end", "end_char", "char_end", "end_offset")
_SPAN_TEXT_KEYS = ("text", "annotated_text", "span_text", "surface")
_LABEL_KEYS = ("label", "tag", "type", "entity", "entity_type")
_SCORE_KEYS = ("score", "confidence", "similarity")

_GIVEN_KEYS = ("given_name", "first_name", "first_names", "given", "given_names", "firstname", "voornaam")
_FAMILY_KEYS = ("family_name", "last_name", "surname", "family", "lastname", "achternaam")
_BIRTH_KEYS = ("birth_date", "birthdate", "birth_dt", "date_of_birth", "dob")
_FULLNAME_KEYS = ("name", "full_name", "fullname")

_LANG_KEYS = ("lang", "language")
_DOC_DATE_KEYS = (
    "document_creation_date", "document_date", "text_creation_date",
    "created_dt_tm", "creation_date", "encounter_date", "created_at",
)
_CAREGIVERS_KEYS = ("caregivers", "doctors")
_RETIRED_IDENTITY_KEYS = ("patient_name", "caregiver_names")


def _first(d: dict[str, Any], keys: tuple[str, ...]) -> tuple[str | None, Any]:
    """Return (matched_key, value) for the first present key, else (None, None)."""
    for k in keys:
        if k in d and d[k] is not None:
            return k, d[k]
    return None, None


def _pop_aliases(d: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Pop the first present alias's value; drop the remaining aliases."""
    value = None
    found = False
    for k in keys:
        if k in d:
            if not found and d[k] is not None:
                value = d[k]
                found = True
            del d[k]
    return value


# --- spans -----------------------------------------------------------------

def normalize_subannotation(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one benchmark segment without treating it as a PII span."""
    item = dict(raw)
    begin = _pop_aliases(item, _BEGIN_KEYS)
    end = _pop_aliases(item, _END_KEYS)
    text = _pop_aliases(item, _SPAN_TEXT_KEYS)
    category = _pop_aliases(item, ("category", "Category", "type"))
    out: dict[str, Any] = {}
    if begin is not None:
        out["begin"] = begin
    if end is not None:
        out["end"] = end
    if text is not None:
        out["text"] = text
    if category is not None:
        out["category"] = category
    out.update(item)
    return out

def normalize_span(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a span variant to ``{begin, end, text, label, category, subtype, ...}``.

    Preserves unknown extras (e.g. ``replacement``, ``confirmed``, ``native_label``).
    """
    span = dict(raw)
    nested_subannotations = span.pop("subannotations", None)

    begin = _pop_aliases(span, _BEGIN_KEYS)
    end = _pop_aliases(span, _END_KEYS)
    # docdeid-style length instead of end
    if end is None and begin is not None and "length" in span:
        try:
            end = int(begin) + int(span["length"])
        except (TypeError, ValueError):
            end = None
    span.pop("length", None)

    text = _pop_aliases(span, _SPAN_TEXT_KEYS)
    label = _pop_aliases(span, _LABEL_KEYS)

    # capitalized Category/Subtype -> lowercase (the workspace-wide fix)
    category = _pop_aliases(span, ("category", "Category"))
    subtype = _pop_aliases(span, ("subtype", "Subtype"))

    # confidence/similarity -> score (only if no explicit score)
    score = _pop_aliases(span, _SCORE_KEYS)

    # derive category/subtype from label, or label from category/subtype
    if label is not None:
        cat_from_label, sub_from_label = split_label(str(label))
        if category in (None, ""):
            category = cat_from_label
        if subtype in (None, ""):
            subtype = sub_from_label
    elif category not in (None, ""):
        label = compose_label(str(category), subtype or None)

    out: dict[str, Any] = {}
    if begin is not None:
        out["begin"] = begin
    if end is not None:
        out["end"] = end
    if text is not None:
        out["text"] = text
    if label is not None:
        out["label"] = label
    if category is not None:
        out["category"] = category
    out["subtype"] = subtype if subtype not in ("",) else None
    if score is not None:
        out["score"] = score
    if isinstance(nested_subannotations, list):
        out["subannotations"] = [
            normalize_subannotation(item) if isinstance(item, dict) else item
            for item in nested_subannotations
        ]
    # keep any remaining extras (replacement, confirmed, native_label, priority, ...)
    out.update(span)
    return out


# --- names / metadata ------------------------------------------------------

def _split_full_name(full: str) -> dict[str, str]:
    """Best-effort ``"Given Middle Family" -> {given_name, family_name}``.

    Heuristic only (last whitespace token = family, the rest = given). Comma
    form ``"Family, Given"`` is handled explicitly. Callers that have the real
    parts should pass them instead of a full string.
    """
    full = full.strip()
    if not full:
        return {}
    if "," in full:
        family, _, given = full.partition(",")
        return {"given_name": given.strip(), "family_name": family.strip()}
    parts = full.split()
    if len(parts) == 1:
        return {"family_name": parts[0]}
    return {"given_name": " ".join(parts[:-1]), "family_name": parts[-1]}


def normalize_name(raw: Any) -> dict[str, Any] | None:
    """Map a name variant to ``{given_name, family_name, birth_date?}``.

    Accepts a dict (given/first/first_names/surname/... aliases), a plain
    full-name string, or ``None``.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        return _split_full_name(raw) or None
    if not isinstance(raw, dict):
        return None

    d = dict(raw)
    given = _pop_aliases(d, _GIVEN_KEYS)
    family = _pop_aliases(d, _FAMILY_KEYS)
    birth = _pop_aliases(d, _BIRTH_KEYS)
    full = _pop_aliases(d, _FULLNAME_KEYS)

    # deduce/docdeid style: first_names is a list, initials separate
    if isinstance(given, list):
        given = " ".join(str(x) for x in given if x)

    out: dict[str, Any] = {}
    if (given in (None, "")) and (family in (None, "")) and full:
        out.update(_split_full_name(str(full)))
    else:
        if given not in (None, ""):
            out["given_name"] = given
        if family not in (None, ""):
            out["family_name"] = family
    if birth not in (None, ""):
        out["birth_date"] = birth
    # preserve remaining extras (initials, aliases, source_paths, ...) — drop source_paths noise
    d.pop("source_paths", None)
    d.pop("initials", None)
    out.update(d)
    return out or None


def normalize_caregivers(raw: Any) -> list[dict[str, Any]] | None:
    """Map a caregivers value (list of dicts, list of strings, or single) to
    ``[{given_name, family_name}, ...]``."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return None
    out: list[dict[str, Any]] = []
    for item in raw:
        name = normalize_name(item)
        if name:
            out.append(name)
    return out or None


def normalize_metadata(raw: Any) -> dict[str, Any]:
    """Map a metadata dict to the canonical shape, preserving unknown extras."""
    if not isinstance(raw, dict):
        return {} if raw is None else {"value": raw}
    meta = dict(raw)

    retired = [key for key in _RETIRED_IDENTITY_KEYS if key in meta]
    if retired:
        raise ValueError(
            f"retired metadata key(s) {retired}; use 'patient' and 'caregivers'"
        )

    lang = _pop_aliases(meta, _LANG_KEYS)
    doc_date = _pop_aliases(meta, _DOC_DATE_KEYS)
    date_shift = _pop_aliases(meta, ("date_shift_days", "date_shift"))

    # patient identity, in priority order of source:
    #  1. an explicit patient object (or full string)
    #  2. flat patient_given_name / patient_last_name / patient_birthdate columns
    #  3. flat metadata carrying bare `name` + `birth_dt` for the patient.
    patient_raw: Any = _pop_aliases(meta, ("patient", "patient_full_name"))
    flat_given = _pop_aliases(meta, ("patient_given_name",))
    flat_family = _pop_aliases(meta, ("patient_last_name", "patient_family_name"))
    flat_birth = _pop_aliases(meta, ("patient_birthdate", "patient_birth_date"))
    meta_name = _pop_aliases(meta, ("name", "full_name"))
    meta_birth = _pop_aliases(meta, ("birth_dt", "birthdate", "birth_date"))

    patient: dict[str, Any] | None = None
    if patient_raw is not None:
        patient = normalize_name(patient_raw)
        if patient is not None and "birth_date" not in patient:
            fallback_birth = flat_birth or meta_birth
            if fallback_birth:
                patient["birth_date"] = fallback_birth
    elif flat_given or flat_family or flat_birth:
        patient = normalize_name(
            {"given_name": flat_given, "family_name": flat_family, "birth_date": flat_birth}
        )
    elif meta_name or meta_birth:
        patient = normalize_name(meta_name) or {}
        if meta_birth:
            patient["birth_date"] = meta_birth
        patient = patient or None

    caregivers_raw = None
    for k in _CAREGIVERS_KEYS + ("caregiver_name",):
        if k in meta:
            v = meta.pop(k)
            if caregivers_raw is None and v is not None:
                caregivers_raw = v
    caregivers = normalize_caregivers(caregivers_raw)

    out: dict[str, Any] = {}
    if lang not in (None, ""):
        out["lang"] = lang
    if doc_date not in (None, ""):
        out["document_creation_date"] = doc_date
    if date_shift is not None:
        out["date_shift_days"] = date_shift
    if patient:
        out["patient"] = patient
    if caregivers:
        out["caregivers"] = caregivers
    # keep everything else (source, synthea_source, document_type, ...)
    out.update(meta)
    return out


# --- records ---------------------------------------------------------------

def normalize_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a full document/record variant to the canonical shape.

    ``document_id`` / ``text`` / ``deid_text`` / ``spans`` / ``metadata`` are
    canonicalized; every other top-level key is preserved (e.g. ``annotated``,
    ``status``, ``warnings``, ``source_dataset``).
    """
    rec = dict(raw)

    forbidden = [key for key in _FORBIDDEN_SPAN_CONTAINER_KEYS if key in rec]
    if forbidden:
        raise ValueError(
            f"non-canonical span container(s) {forbidden}; use the one canonical key 'spans'"
        )
    if "subannotations" in rec:
        raise ValueError("top-level subannotations are non-canonical; nest them in their parent span")

    doc_id = _pop_aliases(rec, _ID_KEYS)
    text = _pop_aliases(rec, _TEXT_KEYS)
    deid_text = _pop_aliases(rec, _DEID_TEXT_KEYS)
    spans_raw = _pop_aliases(rec, _SPANS_KEYS)
    metadata_raw = _pop_aliases(rec, ("metadata",))

    out: dict[str, Any] = {}
    if doc_id is not None:
        out["document_id"] = doc_id
    if text is not None:
        out["text"] = text
    if isinstance(spans_raw, list):
        spans = [normalize_span(s) if isinstance(s, dict) else s for s in spans_raw]
        for span in spans:
            if isinstance(span, dict) and isinstance(span.get("subannotations"), list):
                span["subannotations"].sort(
                    key=lambda item: (
                        int(item.get("begin", -1)) if isinstance(item, dict) else -1,
                        int(item.get("end", -1)) if isinstance(item, dict) else -1,
                    )
                )
        out["spans"] = spans
    if deid_text is not None:  # optional-where-it-exists (D6)
        out["deid_text"] = deid_text
    if metadata_raw is not None:
        out["metadata"] = normalize_metadata(metadata_raw)
    out.update(rec)  # preserve extras
    return out


def normalize(obj: Any) -> Any:
    """Dispatch: a record dict -> normalized record; a list -> element-wise."""
    if isinstance(obj, list):
        return [normalize(x) for x in obj]
    if isinstance(obj, dict):
        return normalize_record(obj)
    return obj
