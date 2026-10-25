"""Data models for the knowledge base: source articles, facts, published articles, chunks."""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Country = Literal["SA", "AE", "EG"]
COUNTRIES: tuple[Country, ...] = ("SA", "AE", "EG")
COUNTRY_NAMES: dict[str, str] = {"SA": "Saudi Arabia", "AE": "UAE", "EG": "Egypt"}

DOC_ID_PATTERN = r"^kb-\d{4}$"


class Category(StrEnum):
    ACCOUNT_KYC = "account_kyc"
    TRANSFERS_PAYMENTS = "transfers_payments"
    REFUNDS_DISPUTES = "refunds_disputes"
    CARDS = "cards"
    FEES_LIMITS = "fees_limits"
    SECURITY = "security"
    TROUBLESHOOTING = "troubleshooting"
    LEGAL_POLICY = "legal_policy"


# Target share of articles per category (spec §5.2).
CATEGORY_TARGET_SHARE: dict[Category, float] = {
    Category.ACCOUNT_KYC: 0.15,
    Category.TRANSFERS_PAYMENTS: 0.20,
    Category.REFUNDS_DISPUTES: 0.15,
    Category.CARDS: 0.15,
    Category.FEES_LIMITS: 0.10,
    Category.SECURITY: 0.10,
    Category.TROUBLESHOOTING: 0.10,
    Category.LEGAL_POLICY: 0.05,
}


class ArticleType(StrEnum):
    FAQ = "faq"
    PROCEDURE = "procedure"
    FEE_TABLE = "fee_table"
    POLICY = "policy"
    TROUBLESHOOTING = "troubleshooting"


class Mess(StrEnum):
    """Deliberate realism tags (spec §5.2 "mandatory realistic mess")."""

    COUNTRY_SPECIFIC = "country_specific"
    BURIED_EXCEPTION = "buried_exception"
    NEAR_DUPLICATE = "near_duplicate"
    SUPERSEDED = "superseded"
    CROSS_REFERENCE = "cross_reference"


class ReviewStatus(StrEnum):
    DRAFT = "draft"  # LLM first draft
    REWRITTEN = "rewritten"  # rewritten by hand (spec Phase 1 step 3)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArticleMeta(_Strict):
    """Front matter of a source article in data/kb/articles/."""

    doc_id: str = Field(pattern=DOC_ID_PATTERN)
    title: str = Field(min_length=3)
    category: Category
    section_path: list[str] = Field(min_length=1)
    countries: list[Country] = Field(min_length=1)
    effective_date: date
    superseded_by: str | None = Field(default=None, pattern=DOC_ID_PATTERN)
    article_type: ArticleType
    status: ReviewStatus = ReviewStatus.DRAFT
    mess: list[Mess] = Field(default_factory=list)


class Article(_Strict):
    """Published record in kb.jsonl (spec §5.2 schema)."""

    doc_id: str
    title: str
    category: Category
    section_path: list[str]
    countries: list[Country]
    effective_date: date
    superseded_by: str | None
    article_type: ArticleType
    text: str


class Fact(_Strict):
    """One row of facts.csv: the single source of truth for every governed value."""

    fact_id: str
    topic: str
    country: Country | Literal["ALL"]
    value: str
    unit: str
    display: str = Field(min_length=1)
    effective_date: date
    superseded_by: str | None = None
    notes: str = ""

    @property
    def expected_id(self) -> str:
        base = f"{self.topic}.{self.country}"
        return f"{base}@{self.effective_date.isoformat()}" if self.superseded_by else base


class Chunk(_Strict):
    """Retrieval unit in chunks.jsonl."""

    chunk_id: str
    doc_id: str
    chunk_index: int
    title: str
    category: Category
    article_type: ArticleType
    section_path: list[str]
    headings: list[str]
    countries: list[Country]
    effective_date: date
    superseded_by: str | None
    text: str  # prefix + body; what gets embedded and BM25-indexed
    body: str  # the passage shown to users as the citation
    n_tokens: int
    body_sha1: str  # detects label drift if the chunker or article text changes
