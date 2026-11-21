"""Input guardrail: the scope must be Brazil (None) or one of the 27 valid UF codes."""

from pydantic import BaseModel, ValidationError, field_validator

from srag.config import VALID_UFS


class InvalidRequestError(ValueError):
    """Raised when the report request is not valid; the agent never runs."""


class ReportRequest(BaseModel):
    """A validated report request. uf=None means all of Brazil."""

    uf: str | None = None

    @field_validator("uf")
    @classmethod
    def uf_must_be_a_valid_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = value.strip().upper()
        if code not in VALID_UFS:
            raise ValueError(f"'{value[:10]}' is not a valid UF code")
        return code


def validate_request(uf: str | None) -> ReportRequest:
    """Return the validated request or raise InvalidRequestError with a clear message."""
    try:
        return ReportRequest(uf=uf)
    except ValidationError as error:
        problem = error.errors()[0]["msg"].removeprefix("Value error, ")
        raise InvalidRequestError(
            f"Invalid request: {problem}. Use one of {', '.join(VALID_UFS)}."
        ) from error
