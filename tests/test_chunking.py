from datetime import date

from musaid.ingest.chunking import (
    chunk_article,
    count_tokens,
    heading_countries,
    parse_blocks,
)
from musaid.ingest.schema import Article


def make(text: str, countries=("SA", "AE", "EG")) -> Article:
    return Article(
        doc_id="kb-0001",
        title="Test article",
        category="cards",
        section_path=["Cards"],
        countries=list(countries),
        effective_date=date(2025, 1, 1),
        superseded_by=None,
        article_type="procedure",
        text=text,
    )


def words(n: int) -> str:
    return " ".join(["word"] * n)


def test_lead_in_list_and_split_list_stay_together():
    md = "To do it:\n\n1. One\n\n2. Two\n\n3. Three\n\nAfter."
    kinds = [(b.kind, b.text) for b in parse_blocks(md)]
    assert kinds == [("list", "To do it:\n\n1. One\n\n2. Two\n\n3. Three"), ("para", "After.")]


def test_table_directly_after_text_is_its_own_block():
    blocks = parse_blocks("Fees below.\n| a | b |\n|---|---|\n| 1 | 2 |")
    assert [b.kind for b in blocks] == ["para", "table"]


def test_heading_countries():
    assert heading_countries("Saudi Arabia") == ("SA",)
    assert heading_countries("Customers in Egypt under 21") == ("EG",)
    assert heading_countries("UAE and KSA") == ("SA", "AE")
    assert heading_countries("Fees") is None


def test_country_sections_are_tagged_and_not_merged():
    md = "Intro.\n\n## Saudi Arabia\n\nA.\n\n## UAE\n\nB.\n\n## Egypt\n\nC."
    chunks = chunk_article(make(md))
    assert [c.countries for c in chunks] == [["SA", "AE", "EG"], ["SA"], ["AE"], ["EG"]]
    assert chunks[1].section_path == ["Cards", "Saudi Arabia"]
    assert chunks[1].text.startswith(
        "Test article\nSection: Cards > Saudi Arabia\nCountries: Saudi Arabia\n\n"
    )


def test_small_sections_are_packed():
    md = "## One\n\nShort.\n\n## Two\n\nAlso short."
    chunks = chunk_article(make(md))
    assert len(chunks) == 1
    assert chunks[0].headings == ["One", "Two"]
    assert chunks[0].section_path == ["Cards"]


def test_large_sections_split_but_never_inside_a_table():
    table = "| a | b |\n|---|---|\n" + "\n".join(f"| {words(10)} | x |" for _ in range(40))
    md = f"## Big\n\n{words(300)}\n\n{table}\n\n{words(300)}"
    chunks = chunk_article(make(md))
    assert any(table in c.body for c in chunks)  # table intact, even though it's oversized
    assert len(chunks) == 3


def test_short_trailing_section_joins_previous_chunk():
    md = f"## Main\n\n{words(250)}\n\n## Note\n\nA short note."
    assert len(chunk_article(make(md))) == 1


def test_ids_and_hash_are_deterministic():
    md = f"## A\n\n{words(250)}\n\n## B\n\n{words(250)}"
    first, second = chunk_article(make(md)), chunk_article(make(md))
    assert [c.chunk_id for c in first] == ["kb-0001#c0", "kb-0001#c1"]
    assert [c.body_sha1 for c in first] == [c.body_sha1 for c in second]


def test_count_tokens():
    assert count_tokens("Fees: SAR 1,000.") == 7
