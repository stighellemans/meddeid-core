"""Language-neutral profile interface shared by language-pack plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol

from .age_policy import AgeGranularityPolicy

PostProcessor = Callable[..., list[dict[str, Any]]]
LookupCategories = Callable[[], tuple[str, ...]]
LookupValues = Callable[[str], tuple[str, ...]]
ResourceManifest = Callable[[], dict[str, Any]]
CapabilityManifest = Callable[[], dict[str, Any]]
DateReplacementKind = Literal["shifted_date", "age_generalized", "year_fallback"]


@dataclass(frozen=True)
class DateReplacement:
    body: str
    kind: DateReplacementKind


class DateReplacementProvider(Protocol):
    def __call__(
        self,
        text: str,
        *,
        label: str,
        date_shift_days: int,
        context_before: str,
        context_after: str,
        document_creation_date: str | None,
        age_granularity_policy: AgeGranularityPolicy,
    ) -> DateReplacement | None: ...


class BirthDateVariantsProvider(Protocol):
    def __call__(self, value: str) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class LanguageProfile:
    profile_id: str
    language_tags: tuple[str, ...]
    post_process_spans: PostProcessor
    lookup_categories_provider: LookupCategories | None = None
    lookup_values_provider: LookupValues | None = None
    resource_manifest_provider: ResourceManifest | None = None
    capability_manifest_provider: CapabilityManifest | None = None
    date_replacement_provider: DateReplacementProvider | None = None
    birth_date_variants_provider: BirthDateVariantsProvider | None = None

    def accepts_language(self, language_tag: str) -> bool:
        normalized = language_tag.strip().replace("_", "-").lower()
        return normalized in {tag.lower() for tag in self.language_tags}

    def validate_language(self, language_tag: str | None) -> None:
        if language_tag and not self.accepts_language(language_tag):
            supported = ", ".join(self.language_tags)
            raise ValueError(
                f"document language {language_tag!r} is incompatible with "
                f"post-process profile {self.profile_id!r}; expected one of: {supported}"
            )

    def lookup_categories(self) -> tuple[str, ...]:
        if self.lookup_categories_provider is None:
            return ()
        return self.lookup_categories_provider()

    def lookup_values(self, category: str) -> tuple[str, ...]:
        if self.lookup_values_provider is None:
            raise KeyError(f"profile {self.profile_id!r} provides no lookup resources")
        return self.lookup_values_provider(category)

    def replace_date(
        self,
        text: str,
        *,
        label: str,
        date_shift_days: int,
        context_before: str,
        context_after: str,
        document_creation_date: str | None,
        age_granularity_policy: AgeGranularityPolicy,
    ) -> DateReplacement | None:
        if self.date_replacement_provider is None:
            return None
        return self.date_replacement_provider(
            text,
            label=label,
            date_shift_days=date_shift_days,
            context_before=context_before,
            context_after=context_after,
            document_creation_date=document_creation_date,
            age_granularity_policy=age_granularity_policy,
        )

    def birth_date_variants(self, value: str) -> tuple[str, ...]:
        if self.birth_date_variants_provider is None:
            raise ValueError(
                f"language profile {self.profile_id!r} does not support patient.birth_date"
            )
        return self.birth_date_variants_provider(value)

    def manifest(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "language_tags": list(self.language_tags),
        }
        if self.resource_manifest_provider is not None:
            resources = self.resource_manifest_provider()
            if resources.get("profile_id") != self.profile_id:
                raise RuntimeError("language resource manifest is scoped to another profile")
            payload["resources"] = resources
        if self.capability_manifest_provider is not None:
            capabilities = self.capability_manifest_provider()
            for name, capability in capabilities.items():
                if capability.get("profile_id", self.profile_id) != self.profile_id:
                    raise RuntimeError(
                        f"language capability {name!r} is scoped to another profile"
                    )
            payload["capabilities"] = capabilities
        return payload
