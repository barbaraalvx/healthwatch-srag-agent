from datetime import date
from pathlib import Path

from srag.audit.sanitize import REDACTED, Sanitizer

SECRET = "sk-ant-abcdef1234567890"


def make_sanitizer(secrets=(SECRET,), max_text_chars: int = 50, max_items: int = 3) -> Sanitizer:
    return Sanitizer(secrets, max_text_chars, max_items)


def test_known_secret_is_redacted_wherever_it_appears():
    cleaned = make_sanitizer().clean({"note": f"key={SECRET}!", "list": [f"{SECRET}"]})

    assert cleaned == {"note": f"key={REDACTED}!", "list": [REDACTED]}


def test_secret_looking_values_are_redacted_even_when_unknown():
    sanitizer = make_sanitizer(secrets=())

    assert sanitizer.clean("a tvly-abcdefghij1234 b") == f"a {REDACTED} b"
    assert sanitizer.clean("Authorization: Bearer abc.def-1234567890") == (
        f"Authorization: {REDACTED}"
    )


def test_secret_field_names_are_redacted_but_token_counters_are_kept():
    cleaned = make_sanitizer().clean(
        {"api_key": "x", "Authorization": "y", "access_token": "z", "max_tokens": 2000}
    )

    assert cleaned == {
        "api_key": REDACTED,
        "Authorization": REDACTED,
        "access_token": REDACTED,
        "max_tokens": 2000,
    }


def test_very_short_secrets_are_ignored_so_normal_words_survive():
    assert make_sanitizer(secrets=("abc",)).clean("abc def") == "abc def"


def test_long_text_is_truncated_with_the_number_of_removed_characters():
    cleaned = make_sanitizer(max_text_chars=10).clean("x" * 25)

    assert cleaned == "x" * 10 + "[+15 chars]"


def test_long_lists_are_truncated_with_the_number_of_removed_items():
    assert make_sanitizer(max_items=2).clean([1, 2, 3, 4]) == [1, 2, "[+2 items]"]


def test_plain_values_are_kept():
    assert make_sanitizer().clean({"a": None, "b": True, "c": 3, "d": 1.5}) == {
        "a": None,
        "b": True,
        "c": 3,
        "d": 1.5,
    }


def test_other_types_become_text():
    cleaned = make_sanitizer().clean({"day": date(2026, 11, 21), "path": Path("reports")})

    assert cleaned == {"day": "2026-11-21", "path": "reports"}


def test_very_deep_structures_are_cut():
    nested: dict = {}
    cursor = nested
    for _ in range(10):
        cursor["child"] = {}
        cursor = cursor["child"]

    assert "[max depth]" in str(make_sanitizer().clean(nested))
