"""Language-neutral profile interface shared by language-pack plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

PostProcessor = Callable[..., list[dict[str, Any]]]
LookupCategories = Callable[[], tuple[str, ...]]
LookupValues = Callable[[str], tuple[str, ...]]
ResourceManifest = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class LanguageProfile:
    profile_id: str
    version: str
    language_tags: tuple[str, ...]
    post_process_spans: PostProcessor
    lookup_categories_provider: LookupCategories | None = None
    lookup_values_provider: LookupValues | None = None
    resource_manifest_provider: ResourceManifest | None = None

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

    def manifest(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "profile_version": self.version,
            "language_tags": list(self.language_tags),
        }
        if self.resource_manifest_provider is not None:
            resources = self.resource_manifest_provider()
            if resources.get("profile_id") != self.profile_id:
                raise RuntimeError("language resource manifest is scoped to another profile")
            payload["resources"] = resources
        return payload

