# meddeid-core

`meddeid-core` provides the language-neutral contracts shared by the MedDeID
suite: the document schema, 15-label data taxonomy, ordered 14-label model head,
record normalization, and character-offset validation.

The [suite documentation](https://stighellemans.github.io/meddeid/concepts/data-contract/)
explains how this contract moves through MedDeID workflows. This repository is
the authority for the schema, taxonomy, label order, and offset rules.

## Installation

```bash
pip install meddeid-core
```

Install the optional Pydantic models with:

```bash
pip install 'meddeid-core[models]'
```

## Python API

```python
from meddeid_core import BERT_ENTITY_LABELS, normalize_record, validate_record

record = normalize_record(record)
validate_record(record)
```

MedDeID uses half-open `[begin, end)` offsets measured in Unicode code points.
The only canonical top-level span container is `spans`.

The core package also owns the language-neutral
`meddeid.age-granularity.v1` JSON contract. `load_age_granularity_policy()`
loads the packaged default, a custom JSON path, or a mapping and returns its
validated calendar generalizer and deterministic identity. Language packages
remain responsible only for parsing and localized rendering.

Benchmark subannotations are nested under their parent primary span. A non-empty
subannotation list must be a complete, contiguous partition of the parent, and
all offsets remain absolute document offsets:

```json
{
  "begin": 0,
  "end": 11,
  "text": "Jan Peeters",
  "label": "Name:Patient",
  "category": "Name",
  "subtype": "Patient",
  "subannotations": [
    {"begin": 0, "end": 3, "text": "Jan", "category": "given"},
    {"begin": 3, "end": 4, "text": " ", "category": "formatting"},
    {"begin": 4, "end": 11, "text": "Peeters", "category": "family"}
  ]
}
```

## Name replacement contract

`DocumentMetadata.name_replacement` is a strict Boolean, default `False`.
The untyped `normalize_metadata()` function rejects strings, numbers and null
for this field too. The runtime uses `True` to replace `Name:Patient`,
`Name:Caregiver` and `Name:Other`; `False` retains their original bracketed labels.

Core owns `meddeid.name-spelling.v1`: normalized spelling and study scope are
encoded deterministically and keyed with HMAC-SHA256. `NameCatalog` accepts
language resources and renders titles, initials and names; core contains no
name lists. Language packs provide the optional `LanguageProfile.replace_name()`
hook, returning an unbracketed body or `None` for a safe label fallback.

`name_configuration()` accepts a key of at least 32 bytes and a nonempty scope,
or reads hexadecimal `MEDDEID_NAME_KEY` and `MEDDEID_NAME_SCOPE`. Keep these in
protected deployment configuration, outside document metadata and shared output.
Pin the algorithm and language resources along with the key and scope to retain
aliases across workers, documents and retries. No person mapping database is
required. Initial periods, Unicode normalization, case and whitespace normalize;
`Mark Peters`, `M. Peters` and `Mark P.` remain different spellings. Aliases can
collide and are not unique patient identifiers or reversible encryption.

## Normalize canonical JSONL

The normalizer standardizes fields within records that use the canonical
`document_id`, `text`, and `spans` containers. For example, it can convert
`start` to `begin`:

```bash
meddeid-normalize-jsonl input.jsonl normalized.jsonl
```

Other top-level span containers, including `annotations`, `entities`,
`deid_spans`, and `items`, are not part of the MedDeID schema and are rejected.

## Taxonomy contract

The Python taxonomy is authoritative. The generated language-neutral contract
is committed at `contracts/taxonomy.json` for JavaScript and non-Python
consumers. After an intentional taxonomy change, regenerate it with:

```bash
python scripts/export_contracts.py
```

Language-specific behavior belongs in packages such as
`meddeid-language-nl`; this package has no language rules or model runtime.

## Development

```bash
pip install -e '.[dev]'
pytest
```

## Licence

AGPL-3.0-only. See `NOTICE` for attribution information.
