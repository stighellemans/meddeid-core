"""Export language-neutral files from the canonical Python contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import taxonomy


def taxonomy_contract() -> dict[str, object]:
    return {
        "contract_version": 1,
        "taxonomy_version": "ProductionLabels-v1.1",
        "categories": list(taxonomy.CATEGORIES),
        "subtypes": list(taxonomy.SUBTYPES),
        "subtypes_by_category": {
            category: list(taxonomy.SUBTYPES_BY_CATEGORY[category])
            for category in taxonomy.CATEGORIES
        },
        "entity_labels": list(taxonomy.ENTITY_LABELS),
        "model_entity_labels": list(taxonomy.BERT_ENTITY_LABELS),
    }


def write_taxonomy_contract(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(taxonomy_contract(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(write_taxonomy_contract(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
