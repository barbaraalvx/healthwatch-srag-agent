"""Small text helpers shared by several modules."""

import unicodedata


def normalize(text: str) -> str:
    """Lower-case text without accents, so 'Síndrome' and 'sindrome' compare equal."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()
