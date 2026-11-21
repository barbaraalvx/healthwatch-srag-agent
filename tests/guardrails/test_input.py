import pytest

from srag.config import VALID_UFS
from srag.guardrails.input import InvalidRequestError, validate_request


def test_no_uf_means_all_of_brazil():
    assert validate_request(None).uf is None


@pytest.mark.parametrize("uf", VALID_UFS)
def test_every_official_uf_is_accepted(uf):
    assert validate_request(uf).uf == uf


@pytest.mark.parametrize(("typed", "expected"), [("sp", "SP"), (" rj ", "RJ"), ("Mg", "MG")])
def test_case_and_surrounding_spaces_are_normalized(typed, expected):
    assert validate_request(typed).uf == expected


@pytest.mark.parametrize(
    "uf", ["XX", "", "BR", "São Paulo", "SPP", "'; DROP TABLE cases; --", "S P"]
)
def test_anything_else_is_rejected(uf):
    with pytest.raises(InvalidRequestError):
        validate_request(uf)


def test_wrong_type_is_rejected():
    with pytest.raises(InvalidRequestError):
        validate_request(123)


def test_message_is_clear_and_lists_the_valid_codes():
    with pytest.raises(InvalidRequestError) as raised:
        validate_request("XX")

    message = str(raised.value)
    assert "'XX' is not a valid UF code" in message
    assert "SP" in message and "TO" in message


def test_rejected_value_is_cut_in_the_message():
    with pytest.raises(InvalidRequestError) as raised:
        validate_request("A" * 500)

    assert "A" * 11 not in str(raised.value)
