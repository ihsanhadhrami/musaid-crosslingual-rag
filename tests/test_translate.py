"""Query translation: routing, cache, cost. No network: the API client is stubbed."""

from datetime import UTC, datetime

from musaid.translate.llm import (
    Translation,
    TranslationCache,
    is_peak,
    needs_translation,
    translate_all,
    translation_stats,
)


def rec(source, text="t", created="2026-11-14T12:00:00+00:00", **kw):
    base = dict(
        source=source, text=text, model="deepseek-flash", prompt_version="v1",
        input_tokens=200, cached_input_tokens=0, output_tokens=20, latency_ms=500.0,
        created=created,
    )  # fmt: skip
    return Translation(**(base | kw))


def test_only_arabic_script_is_translated():
    assert needs_translation("متى ترجع فلوسي؟")
    assert needs_translation("الـ card حقي blocked")  # code-switched
    assert not needs_translation("Where is my refund? 800 SAR")


def test_peak_hours():
    assert is_peak(datetime(2026, 11, 16, 7, 0, tzinfo=UTC))  # Monday 07:00 UTC
    assert not is_peak(datetime(2026, 11, 16, 5, 0, tzinfo=UTC))
    assert not is_peak(datetime(2026, 11, 15, 7, 0, tzinfo=UTC))  # Sunday


def test_cost_is_halved_off_peak():
    peak = rec("x", created="2026-11-16T07:00:00+00:00")
    off = rec("x", created="2026-11-15T07:00:00+00:00")
    assert abs(peak.cost_usd() - (200 * 0.30 + 20 * 1.20) / 1e6) < 1e-12
    assert abs(off.cost_usd() - peak.cost_usd() / 2) < 1e-12


def test_translate_all_uses_cache_and_skips_english(tmp_path):
    calls = []

    class Stub:
        def translate(self, text):
            calls.append(text)
            return rec(text, text="EN:" + text)

    path = tmp_path / "cache.jsonl"
    texts = ["How much?", "كم الرسوم؟", "كم الرسوم؟"]
    out, records = translate_all(texts, TranslationCache(path), "deepseek-flash", "v1", Stub)
    assert out == ["How much?", "EN:كم الرسوم؟", "EN:كم الرسوم؟"]
    assert calls == ["كم الرسوم؟"]  # deduplicated, English never sent
    assert records[0] is None

    def no_api():
        raise AssertionError("cached run must not build a translator")

    out2, _ = translate_all(texts, TranslationCache(path), "deepseek-flash", "v1", no_api)
    assert out2 == out


def test_stats_average_cost_over_all_queries():
    s = translation_stats([None, rec("a"), rec("b", latency_ms=1500.0)])
    assert s["queries"] == 3 and s["translated"] == 2
    assert s["mean_latency_ms"] == 1000.0
    assert s["mean_added_latency_ms"] == round(2000 / 3, 1)
