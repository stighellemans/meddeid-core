from datetime import date
import json

import pytest

from meddeid_core.age_policy import (
    AgePart,
    load_age_granularity_policy,
    policy_from_mapping,
)


def test_default_policy_preserves_existing_suite_boundaries() -> None:
    policy = load_age_granularity_policy()
    reference = date(2026, 5, 14)
    assert policy.generalize(date(2026, 4, 16), reference) == (AgePart(28, "day"),)
    assert policy.generalize(date(2026, 3, 15), reference) == (
        AgePart(8, "week"), AgePart(4, "day")
    )
    assert policy.generalize(date(2025, 11, 14), reference) == (AgePart(6, "month"),)
    assert policy.generalize(date(2014, 5, 15), reference) == (
        AgePart(11, "year"), AgePart(11, "month")
    )
    assert policy.generalize(date(2013, 5, 15), reference) == (AgePart(12, "year"),)


def test_custom_policy_changes_granularity_without_language_code() -> None:
    policy = policy_from_mapping(
        {
            "schema_version": "meddeid.age-granularity.v1",
            "policy_id": "weeks-only",
            "policy_version": "1",
            "bands": [{"output": ["week"]}],
        }
    )
    assert policy.generalize(date(2026, 1, 1), date(2026, 2, 1)) == (
        AgePart(4, "week"),
    )


def test_policy_hash_is_canonical_and_file_loader_matches(tmp_path) -> None:
    payload = {
        "schema_version": "meddeid.age-granularity.v1",
        "policy_id": "example",
        "policy_version": "2",
        "bands": [{"output": ["year"]}],
    }
    first = policy_from_mapping(payload)
    second = policy_from_mapping(dict(reversed(tuple(payload.items()))))
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
    assert first.identity == second.identity == load_age_granularity_policy(path).identity


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "schema_version": "wrong", "policy_id": "x", "policy_version": "1",
            "bands": [{"output": ["year"]}],
        },
        {
            "schema_version": "meddeid.age-granularity.v1", "policy_id": "x",
            "policy_version": "1",
            "bands": [{"output": ["year"]}, {"output": ["month"]}],
        },
        {
            "schema_version": "meddeid.age-granularity.v1", "policy_id": "x",
            "policy_version": "1", "bands": [{"output": ["day", "month"]}],
        },
    ],
)
def test_invalid_policies_fail_fast(payload) -> None:
    with pytest.raises((TypeError, ValueError)):
        policy_from_mapping(payload)


def test_future_birthdate_is_not_rendered_and_leap_dates_are_calendar_safe() -> None:
    policy = load_age_granularity_policy()
    assert policy.generalize(date(2027, 1, 1), date(2026, 1, 1)) is None
    assert policy.generalize(date(2024, 2, 29), date(2026, 2, 28)) == (
        AgePart(2, "year"),
    )
