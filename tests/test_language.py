import pytest

from meddeid_core.language import LanguageProfile


def test_language_profile_contract_is_neutral_and_validates_tags():
    profile = LanguageProfile(
        profile_id="example-XX",
        version="1",
        language_tags=("xx", "xx-YY"),
        post_process_spans=lambda spans, text, metadata: spans,
    )
    profile.validate_language("xx_YY")
    assert profile.lookup_categories() == ()
    assert profile.manifest()["profile_id"] == "example-XX"
    with pytest.raises(ValueError, match="incompatible"):
        profile.validate_language("nl-BE")


def test_language_profile_rejects_capability_for_another_profile():
    profile = LanguageProfile(
        profile_id="example-XX",
        version="1",
        language_tags=("xx",),
        post_process_spans=lambda *args: [],
        capability_manifest_provider=lambda: {
            "subannotation": {"profile_id": "other-YY", "profile_version": "1"}
        },
    )
    with pytest.raises(RuntimeError, match="another profile"):
        profile.manifest()
