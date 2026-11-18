"""Language-neutral, study-scoped name derivation; no person mapping state."""

from __future__ import annotations

import hmac
import json
import os
import re
import unicodedata
from collections.abc import Iterable

NAME_ALGORITHM = "meddeid.name-spelling.v1"
INITIALS = re.compile(r"(?:[^\W\d_]\.)+|[^\W\d_]", re.UNICODE)


def normalize_name_spelling(value: str) -> str:
    """Normalize Unicode, whitespace, case and optional periods on initials."""
    value = unicodedata.normalize("NFC", " ".join(value.split())).casefold()
    return " ".join(
        token.replace(".", "") if INITIALS.fullmatch(token) else token
        for token in value.split()
    )


def name_configuration(
    key: bytes | None = None, scope: str | None = None
) -> tuple[bytes, str]:
    """Resolve explicit settings or the process's MEDDEID_NAME_KEY/SCOPE.

    The environment key is hexadecimal. No key is generated automatically and
    neither names nor derived aliases are cached. Configure once per study/job.
    """
    if key is None:
        try:
            key = bytes.fromhex(os.environ.get("MEDDEID_NAME_KEY", ""))
        except ValueError:
            raise ValueError(
                "MEDDEID_NAME_KEY must contain a hexadecimal name key"
            ) from None
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("Name replacement requires a name key of at least 32 bytes")
    if scope is None:
        scope = os.environ.get("MEDDEID_NAME_SCOPE", "")
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("Name replacement requires a nonempty study scope")
    return key, scope


def name_digest(spelling: str, *, key: bytes, scope: str) -> bytes:
    """Derive stable selection bytes, compatible with UZA name-spelling v1.

    Language providers remove recognized titles before calling this function
    and select/render names from their pinned resources using its output.
    """
    key, scope = name_configuration(key, scope)
    subject = normalize_name_spelling(spelling)
    if not subject:
        raise ValueError("Name spelling must not be empty")
    message = json.dumps(
        [NAME_ALGORITHM, scope, subject], ensure_ascii=False, separators=(",", ":")
    ).encode()
    return hmac.digest(key, message, "sha256")


class NameCatalog:
    """Read-only language resources for spelling-based aliases, with no person cache.

    Resource ordering is part of the mapping. Language packs supply their own
    titles and surname particles; the default renderer retains the UZA v1 output.
    """

    def __init__(
        self,
        first_names: Iterable[str],
        family_names: Iterable[str],
        *,
        prefixes: Iterable[str] = (),
        surname_particles: Iterable[str] = (),
        suffixes: Iterable[str] = (),
    ) -> None:
        self.first_names = self._catalog(first_names)
        self.family_names = self._catalog(family_names)
        self.given_names = frozenset(self._normal(v) for v in self.first_names)
        self.surname_particles = tuple(self._normal(v) for v in surname_particles)
        titles = sorted(prefixes, key=len, reverse=True)
        self.prefix_pattern = (
            re.compile(
                r"^(?:(?:" + "|".join(re.escape(v) for v in titles) + r")\s+)+",
                re.IGNORECASE,
            )
            if titles
            else None
        )
        endings = sorted(suffixes, key=len, reverse=True)
        self.suffix_pattern = (
            re.compile(
                r"(?:[, ]+(?:" + "|".join(re.escape(v) for v in endings) + r"))+$",
                re.IGNORECASE,
            )
            if endings
            else None
        )

    @staticmethod
    def _normal(value: str) -> str:
        return unicodedata.normalize("NFC", " ".join(value.split())).casefold()

    @classmethod
    def _catalog(cls, values: Iterable[str]) -> tuple[str, ...]:
        names = {}
        for raw in values:
            value = unicodedata.normalize("NFC", raw.strip())
            if (
                value
                and value[0].isalpha()
                and all(c.isalpha() or c in " -'’" for c in value)
            ):
                names.setdefault(cls._normal(value), value)
        if not names:
            raise ValueError("Empty name catalog")
        return tuple(names.values())

    @classmethod
    def _choose(cls, catalog: tuple[str, ...], number: int, original: str) -> str:
        original = " " + original + " "
        for step in range(len(catalog)):
            candidate = catalog[(number + step) % len(catalog)]
            if " " + cls._normal(candidate) + " " not in original:
                return candidate
        raise ValueError("Name catalog contains no replacement for this spelling")

    @staticmethod
    def _initials(surface: str, first: str, digest: bytes) -> str:
        from itertools import chain, cycle

        letters = chain(first, cycle(chr(65 + value % 26) for value in digest))
        return "".join(next(letters) if char.isalpha() else char for char in surface)

    def catalog_id(self) -> str:
        import hashlib

        values = [self.first_names, self.family_names]
        return hashlib.sha256(
            json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()

    def replace(self, surface: str, *, key: bytes, scope: str) -> str | None:
        """Return an unbracketed alias body, or None for a safe label fallback."""
        surface = unicodedata.normalize("NFC", " ".join(surface.split()))
        prefix = self.prefix_pattern.match(surface) if self.prefix_pattern else None
        title = prefix[0] if prefix else ""
        body = surface[len(title) :]
        ending = self.suffix_pattern.search(body) if self.suffix_pattern else None
        suffix = ending[0] if ending else ""
        if ending:
            body = body[: ending.start()]
        if (
            not any(c.isalpha() for c in body)
            or len(body) > 200
            or not all(c.isalpha() or c in " .-'’" for c in body)
        ):
            return None
        original = self._normal(body)
        digest = name_digest(body, key=key, scope=scope)
        given = self._choose(
            self.first_names, int.from_bytes(digest[:8], "big"), original
        )
        family = self._choose(
            self.family_names, int.from_bytes(digest[8:16], "big"), original
        )
        tokens = body.split()
        if all(INITIALS.fullmatch(token) for token in tokens):
            output = self._initials(body, given[0].upper(), digest)
        elif INITIALS.fullmatch(tokens[0]):
            boundary = next(
                i for i, token in enumerate(tokens) if not INITIALS.fullmatch(token)
            )
            output = (
                self._initials(" ".join(tokens[:boundary]), given[0].upper(), digest)
                + " "
                + family
            )
        elif INITIALS.fullmatch(tokens[-1]):
            boundary = len(tokens) - 1
            while boundary > 0 and INITIALS.fullmatch(tokens[boundary - 1]):
                boundary -= 1
            output = (
                given
                + " "
                + self._initials(" ".join(tokens[boundary:]), family[0].upper(), digest)
            )
        elif len(tokens) == 1:
            output = given if original in self.given_names else family
        elif any(original.startswith(part + " ") for part in self.surname_particles):
            output = family
        else:
            output = given + " " + family
        if body.isupper():
            output = output.upper()
        elif body.islower():
            output = output.lower()
        if self._normal(output) == original:
            return None
        return title + output + suffix
