from concurrent.futures import ThreadPoolExecutor

import pytest

from meddeid_core.models import DocumentMetadata
from meddeid_core.normalize import normalize_metadata
from meddeid_core.name_pseudonyms import name_configuration, name_digest, NameCatalog

KEY = bytes(range(32))


def test_keyed_derivation_normalizes_spelling_and_separates_scope():
    expected = name_digest("Mark Peters", key=KEY, scope="study-a")
    assert (
        expected.hex()
        == "ca2c249764120ebd3351b5fc62f4e21a7bb33d5d9abfe18cd44a96ac6215fe9f"
    )
    assert name_digest("  MARK   PETERS ", key=KEY, scope="study-a") == expected
    assert name_digest("M. Peters", key=KEY, scope="study-a") == name_digest(
        "M Peters", key=KEY, scope="study-a"
    )
    assert name_digest("Mark P.", key=KEY, scope="study-a") != expected
    assert name_digest("Mark Peters", key=KEY, scope="study-b") != expected
    assert name_digest("Mark Peters", key=b"x" * 32, scope="study-a") != expected
    assert name_digest("Zoe\u0308", key=KEY, scope="study-a") == name_digest(
        "Zoë", key=KEY, scope="study-a"
    )
    with ThreadPoolExecutor(4) as workers:
        assert set(
            workers.map(
                lambda _: name_digest("Mark Peters", key=KEY, scope="study-a"),
                range(30),
            )
        ) == {expected}


def test_configuration_never_generates_or_echoes_a_secret(monkeypatch):
    monkeypatch.delenv("MEDDEID_NAME_KEY", raising=False)
    monkeypatch.delenv("MEDDEID_NAME_SCOPE", raising=False)
    with pytest.raises(ValueError, match="32 bytes"):
        name_configuration()
    monkeypatch.setenv("MEDDEID_NAME_KEY", "secret-not-hex")
    with pytest.raises(ValueError) as error:
        name_configuration()
    assert "secret-not-hex" not in str(error.value)
    monkeypatch.setenv("MEDDEID_NAME_KEY", KEY.hex())
    with pytest.raises(ValueError, match="scope"):
        name_configuration()
    monkeypatch.setenv("MEDDEID_NAME_SCOPE", "study-a")
    assert name_configuration() == (KEY, "study-a")
    assert name_configuration(b"z" * 32, "study-b") == (b"z" * 32, "study-b")


@pytest.mark.parametrize("value", [None, 0, 1, "false", "true", [], {}])
def test_name_boolean_is_strict_in_typed_and_untyped_contract(value):
    with pytest.raises(ValueError):
        normalize_metadata({"name_replacement": value})
    with pytest.raises(ValueError):
        DocumentMetadata(name_replacement=value)


def test_default_and_explicit_booleans():
    assert DocumentMetadata().name_replacement is False
    for value in (False, True):
        assert (
            normalize_metadata({"name_replacement": value})["name_replacement"] is value
        )
        assert DocumentMetadata(name_replacement=value).name_replacement is value


def test_catalog_does_not_reproduce_source_components_and_fails_closed():
    catalog = NameCatalog(["Mark", "Jacob"], ["Peters", "Jones"], prefixes=["Dr."])
    assert catalog.replace("Mark Peters", key=KEY, scope="study-a") == "Jacob Jones"
    assert (
        catalog.replace("Dr. Mark Peters", key=KEY, scope="study-a")
        == "Dr. Jacob Jones"
    )
    assert catalog.replace("<unknown>", key=KEY, scope="study-a") is None
    assert catalog.replace("[Jacob Jones]", key=KEY, scope="study-a") is None
    assert catalog.replace("A" * 201, key=KEY, scope="study-a") is None
    initials = catalog.replace("A." * 80, key=KEY, scope="study-a")
    assert initials is not None and len(initials) == 160
