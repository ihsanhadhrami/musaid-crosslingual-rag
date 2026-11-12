"""Evaluation query records (spec §5.4, rules in docs/ANNOTATION.md)."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from musaid.ingest.schema import Country

QID_PATTERN = r"^q-\d{4}$"
PARALLEL_GROUP_PATTERN = r"^pg-\d{3}$"
CHUNK_ID_PATTERN = r"^kb-\d{4}#c\d+$"


class Variety(StrEnum):
    ENGLISH = "english"
    MSA = "msa"
    GULF = "gulf"
    LEVANTINE_EGYPTIAN = "levantine_egyptian"
    CODE_SWITCHED = "code_switched"
    ARABIZI = "arabizi"


# Target share of the non-parallel queries (spec §5.4).
VARIETY_TARGET_SHARE: dict[Variety, float] = {
    Variety.ENGLISH: 0.30,
    Variety.MSA: 0.20,
    Variety.GULF: 0.18,
    Variety.LEVANTINE_EGYPTIAN: 0.12,
    Variety.CODE_SWITCHED: 0.12,
    Variety.ARABIZI: 0.08,
}


class QueryType(StrEnum):
    """In precedence order (ANNOTATION.md §4): when two apply, the earlier one wins."""

    UNANSWERABLE = "unanswerable"
    AMBIGUOUS = "ambiguous"
    SUPERSEDED_TRAP = "superseded_trap"
    MULTI_HOP = "multi_hop"
    NUMBER_SENSITIVE = "number_sensitive"
    COUNTRY_SPECIFIC = "country_specific"
    TROUBLESHOOTING = "troubleshooting"
    PROCEDURAL = "procedural"
    POLICY_ELIGIBILITY = "policy_eligibility"
    FACTUAL = "factual"


class UnanswerableReason(StrEnum):
    NOT_IN_KB = "not_in_kb"
    ACCOUNT_SPECIFIC = "account_specific"
    OUT_OF_DOMAIN = "out_of_domain"


Script = Literal["arabic", "latin", "mixed"]
GoldSource = Literal["rewritten", "draft", "mixed"]
Difficulty = Literal["easy", "medium", "hard"]
Split = Literal["dev", "test"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QuerySource(_Strict):
    """What an annotator writes in data/eval/source/*.yaml."""

    qid: str = Field(pattern=QID_PATTERN)
    query: str = Field(min_length=3)
    variety: Variety
    type: QueryType
    country: Country | None = None
    answerable: bool = True
    needs_clarification: bool = False
    unanswerable_reason: UnanswerableReason | None = None
    gold_chunk_ids: list[str] = Field(default_factory=list, max_length=3)
    reference_answer: str = ""
    critical_facts: list[str] = Field(default_factory=list, max_length=4)
    parallel_group: str | None = Field(default=None, pattern=PARALLEL_GROUP_PATTERN)
    about_old_policy: bool = False  # explicitly asks about a superseded edition (max 5)
    difficulty: Difficulty
    verified: bool = False
    notes: str = ""


class Query(_Strict):
    """Published record in queries.jsonl / dev.jsonl / test.jsonl."""

    qid: str
    query: str
    variety: Variety
    script: Script
    type: QueryType
    country: Country | None
    answerable: bool
    needs_clarification: bool
    unanswerable_reason: UnanswerableReason | None
    gold_chunk_ids: list[str]
    gold_source: GoldSource | None
    reference_answer: str
    critical_facts: list[str]
    parallel_group: str | None
    about_old_policy: bool
    difficulty: Difficulty
    split: Split | None = None
