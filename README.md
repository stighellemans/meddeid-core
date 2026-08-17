# meddeid-core

`meddeid-core` provides the language-neutral contracts shared by the MedDeID
suite: the document schema, 15-label data taxonomy, ordered 14-label model head,
record normalization, and character-offset validation.

The [suite documentation](https://stighellemans.github.io/meddeid.github.io/concepts/data-contract/)
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
