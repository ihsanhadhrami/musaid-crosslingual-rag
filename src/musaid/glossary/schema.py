"""Data model for the Arabic → English support terminology glossary (spec §5.3)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CONCEPT_ID_PATTERN = r"^[a-z0-9]+(?:_[a-z0-9]+)*$"

# Keys of `variants`, in the order the spec lists them.
ARABIC_SCRIPT_VARIETIES = ("msa", "gulf", "levantine_egyptian")
VARIETIES = (*ARABIC_SCRIPT_VARIETIES, "arabizi")

# KB categories plus "general" for terms that cut across all of them (account, fee, app).
GlossaryCategory = Literal[
    "general",
    "account_kyc",
    "transfers_payments",
    "refunds_disputes",
    "cards",
    "fees_limits",
    "security",
    "troubleshooting",
    "legal_policy",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Variants(_Strict):
    """How customers say the concept. Every variety needs at least one form."""

    msa: list[str] = Field(min_length=1)
    gulf: list[str] = Field(min_length=1)
    levantine_egyptian: list[str] = Field(min_length=1)
    arabizi: list[str] = Field(min_length=1)

    def items(self) -> list[tuple[str, list[str]]]:
        return [(v, getattr(self, v)) for v in VARIETIES]


class GlossaryEntry(_Strict):
    """One concept: the KB's wording and the ways customers ask about it.

    `kb_term` and every `kb_aliases` item must appear verbatim in the KB, so the glossary
    always points the translator at words the retriever can actually match.
    """

    concept_id: str = Field(pattern=CONCEPT_ID_PATTERN)
    kb_term: str = Field(min_length=2)
    kb_aliases: list[str] = Field(default_factory=list)
    category: GlossaryCategory
    variants: Variants
    notes: str = ""
