"""Dependency-free, suite-wide age-granularity policy support."""

from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal, Mapping


AgeUnit = Literal["year", "month", "week", "day"]
_AGE_UNITS = frozenset({"year", "month", "week", "day"})
_BOUNDARY_UNITS = frozenset({"year", "month", "day"})
_BOUNDARY_ORDER = {"day": 0, "month": 1, "year": 2}
_OUTPUT_ORDER = {"year": 0, "month": 1, "week": 2, "day": 3}
AGE_POLICY_SCHEMA_VERSION = "meddeid.age-granularity.v1"


@dataclass(frozen=True)
class AgePart:
    value: int
    unit: AgeUnit


@dataclass(frozen=True)
class AgePolicyIdentity:
    policy_id: str
    policy_version: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class _Boundary:
    value: int
    unit: Literal["year", "month", "day"]
    inclusive: bool


@dataclass(frozen=True)
class _Band:
    until: _Boundary | None
    output: tuple[AgeUnit, ...]


@dataclass(frozen=True)
class AgeGranularityPolicy:
    schema_version: str
    policy_id: str
    policy_version: str
    bands: tuple[_Band, ...]
    identity: AgePolicyIdentity

    def generalize(
        self, birthdate: date, reference_date: date
    ) -> tuple[AgePart, ...] | None:
        """Return age parts at the first matching configured granularity."""
        if birthdate > reference_date:
            return None
        years, months, _ = calendar_age_parts(birthdate, reference_date)
        total_days = (reference_date - birthdate).days
        total_months = years * 12 + months
        values = {"day": total_days, "month": total_months, "year": years}
        for band in self.bands:
            boundary = band.until
            if boundary is None:
                return decompose_age(birthdate, reference_date, band.output)
            actual = values[boundary.unit]
            if actual < boundary.value or (
                boundary.inclusive and actual == boundary.value
            ):
                return decompose_age(birthdate, reference_date, band.output)
        raise RuntimeError("validated age policy has no catch-all band")


def add_years_clamped(value: date, years: int) -> date:
    year = value.year + years
    day = min(value.day, calendar.monthrange(year, value.month)[1])
    return date(year, value.month, day)


def add_months_clamped(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def calendar_age_parts(birthdate: date, reference_date: date) -> tuple[int, int, int]:
    if birthdate > reference_date:
        raise ValueError("birthdate must not be after the reference date")
    years = reference_date.year - birthdate.year
    if add_years_clamped(birthdate, years) > reference_date:
        years -= 1
    anniversary = add_years_clamped(birthdate, years)
    months = 0
    while add_months_clamped(anniversary, months + 1) <= reference_date:
        months += 1
    month_anniversary = add_months_clamped(anniversary, months)
    return years, months, (reference_date - month_anniversary).days


def decompose_age(
    birthdate: date,
    reference_date: date,
    output: tuple[AgeUnit, ...],
) -> tuple[AgePart, ...]:
    """Decompose an interval from coarse to fine configured units."""
    cursor = birthdate
    rendered: list[AgePart] = []
    for index, unit in enumerate(output):
        if unit == "year":
            value = reference_date.year - cursor.year
            if add_years_clamped(cursor, value) > reference_date:
                value -= 1
            cursor = add_years_clamped(cursor, value)
        elif unit == "month":
            value = (reference_date.year - cursor.year) * 12 + (
                reference_date.month - cursor.month
            )
            if add_months_clamped(cursor, value) > reference_date:
                value -= 1
            cursor = add_months_clamped(cursor, value)
        elif unit == "week":
            value = (reference_date - cursor).days // 7
            cursor += timedelta(days=value * 7)
        else:
            value = (reference_date - cursor).days
            cursor += timedelta(days=value)
        if index == 0 or value:
            rendered.append(AgePart(value=value, unit=unit))
    return tuple(rendered)


def birthdate_from_age_parts(
    reference_date: date, parts: tuple[AgePart, ...]
) -> date:
    """Anchor parsed age parts to a deterministic calendar birthdate."""
    result = reference_date
    for part in parts:
        if part.value < 0:
            raise ValueError("age parts must be non-negative")
        if part.unit == "year":
            result = add_years_clamped(result, -part.value)
        elif part.unit == "month":
            result = add_months_clamped(result, -part.value)
        elif part.unit == "week":
            result -= timedelta(days=part.value * 7)
        else:
            result -= timedelta(days=part.value)
    return result


def _canonical_payload(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"age policy {key} must be a non-empty string")
    return value.strip()


def policy_from_mapping(payload: Mapping[str, Any]) -> AgeGranularityPolicy:
    if not isinstance(payload, Mapping):
        raise TypeError("age policy must be a JSON object")
    unexpected_top_level = set(payload) - {
        "schema_version", "policy_id", "policy_version", "bands"
    }
    if unexpected_top_level:
        raise ValueError(
            f"age policy has unknown fields: {sorted(unexpected_top_level)}"
        )
    schema_version = _required_string(payload, "schema_version")
    if schema_version != AGE_POLICY_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported age policy schema {schema_version!r}; "
            f"expected {AGE_POLICY_SCHEMA_VERSION!r}"
        )
    policy_id = _required_string(payload, "policy_id")
    policy_version = _required_string(payload, "policy_version")
    raw_bands = payload.get("bands")
    if not isinstance(raw_bands, list) or not raw_bands:
        raise ValueError("age policy bands must be a non-empty list")

    bands: list[_Band] = []
    previous_boundary: _Boundary | None = None
    for index, raw_band in enumerate(raw_bands):
        if not isinstance(raw_band, Mapping):
            raise ValueError(f"age policy bands[{index}] must be an object")
        unexpected = set(raw_band) - {"until", "output"}
        if unexpected:
            raise ValueError(
                f"age policy bands[{index}] has unknown fields: {sorted(unexpected)}"
            )
        raw_output = raw_band.get("output")
        if not isinstance(raw_output, list) or not raw_output:
            raise ValueError(f"age policy bands[{index}].output must be non-empty")
        output: list[AgeUnit] = []
        for unit in raw_output:
            if unit not in _AGE_UNITS:
                raise ValueError(
                    f"age policy bands[{index}].output contains unsupported unit {unit!r}"
                )
            output.append(unit)
        if len(set(output)) != len(output):
            raise ValueError(f"age policy bands[{index}].output contains duplicates")
        if [_OUTPUT_ORDER[unit] for unit in output] != sorted(
            _OUTPUT_ORDER[unit] for unit in output
        ):
            raise ValueError(
                f"age policy bands[{index}].output must be ordered coarse to fine"
            )

        raw_until = raw_band.get("until")
        boundary: _Boundary | None = None
        if raw_until is None:
            if index != len(raw_bands) - 1:
                raise ValueError("only the final age policy band may omit until")
        else:
            if index == len(raw_bands) - 1:
                raise ValueError("the final age policy band must be a catch-all")
            if not isinstance(raw_until, Mapping):
                raise ValueError(f"age policy bands[{index}].until must be an object")
            unexpected_until = set(raw_until) - {"value", "unit", "inclusive"}
            if unexpected_until:
                raise ValueError(
                    f"age policy bands[{index}].until has unknown fields: "
                    f"{sorted(unexpected_until)}"
                )
            value = raw_until.get("value")
            unit = raw_until.get("unit")
            inclusive = raw_until.get("inclusive")
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"age policy bands[{index}].until.value must be a positive integer"
                )
            if unit not in _BOUNDARY_UNITS:
                raise ValueError(
                    f"age policy bands[{index}].until.unit must be day, month, or year"
                )
            if not isinstance(inclusive, bool):
                raise ValueError(
                    f"age policy bands[{index}].until.inclusive must be boolean"
                )
            boundary = _Boundary(value=value, unit=unit, inclusive=inclusive)
            if previous_boundary is not None:
                previous_rank = _BOUNDARY_ORDER[previous_boundary.unit]
                current_rank = _BOUNDARY_ORDER[boundary.unit]
                if current_rank < previous_rank or (
                    current_rank == previous_rank
                    and boundary.value <= previous_boundary.value
                ):
                    raise ValueError("age policy boundaries must be strictly ordered")
            previous_boundary = boundary
        bands.append(_Band(until=boundary, output=tuple(output)))

    if bands[-1].until is not None:
        raise ValueError("age policy requires one final catch-all band")
    canonical = _canonical_payload(payload)
    identity = AgePolicyIdentity(
        policy_id=policy_id,
        policy_version=policy_version,
        sha256=sha256(canonical).hexdigest(),
    )
    return AgeGranularityPolicy(
        schema_version=schema_version,
        policy_id=policy_id,
        policy_version=policy_version,
        bands=tuple(bands),
        identity=identity,
    )


def load_age_granularity_policy(
    source: AgeGranularityPolicy | str | Path | Mapping[str, Any] | None = None,
) -> AgeGranularityPolicy:
    if isinstance(source, AgeGranularityPolicy):
        return source
    if source is None:
        content = files("meddeid_core").joinpath(
            "resources", "default_age_granularity.json"
        ).read_text(encoding="utf-8")
        payload = json.loads(content)
    elif isinstance(source, Mapping):
        payload = dict(source)
    else:
        path = Path(source).expanduser()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid age policy JSON in {path}: {exc.msg}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("age policy JSON root must be an object")
    return policy_from_mapping(payload)
