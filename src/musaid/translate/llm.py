"""Query translation to English with an LLM (spec Phase 4, ablation #4 onwards).

The translator is DeepSeek (`deepseek-flash`, OpenAI-compatible chat API, thinking off).
Every translation is cached in eval/translations/<name>.jsonl, which is committed: reruns
cost nothing and anyone can reproduce a run without an API key. Each record keeps the
token counts and latency of the original call, so cost and latency per query can be
reported from the cache.

Only queries with Arabic letters are sent. English queries pass through untouched; the
decision uses the script, never the gold variety label.
"""

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

PROMPT_VERSION = "v1"

# v1 is a plain translation prompt with no glossary: ablation #8 adds the glossary, so
# support terminology is deliberately not taught here.
SYSTEM_PROMPT = """\
You translate customer messages written to the support team of a digital wallet app \
into English. The message may be in Modern Standard Arabic, a dialect (Gulf, Egyptian or \
other), or Arabic mixed with English words.

Rules:
- Translate the meaning faithfully, as a native English speaker would write the same \
message. Don't answer it, explain it or add anything.
- Keep every number, amount, currency, date, duration and percentage exactly. Write \
digits as Western digits (0-9).
- Keep names of people, places, banks, apps and services as they are, in their usual \
English spelling.
- Keep English words that are already in the message.
- Output only the English translation, on one line."""

_ARABIC_LETTER = re.compile(r"[ء-ي]")

# USD per 1M tokens, from https://api-docs.deepseek.com/quick_start/pricing (checked
# 2026-11-15). Off-peak is half of peak. Peak: 01:00-04:00 and 06:00-10:00 UTC, Mon-Fri
# (Chinese public holidays, which are off-peak, are ignored here).
PRICES = {
    "deepseek-flash": {"input_hit": 0.006, "input_miss": 0.30, "output": 1.20},
    "deepseek-v4-pro": {"input_hit": 0.044, "input_miss": 1.32, "output": 3.96},
}


def needs_translation(text: str) -> bool:
    return bool(_ARABIC_LETTER.search(text))


def is_peak(ts: datetime) -> bool:
    ts = ts.astimezone(UTC)
    return ts.weekday() < 5 and (1 <= ts.hour < 4 or 6 <= ts.hour < 10)


@dataclass(frozen=True)
class Translation:
    source: str
    text: str
    model: str
    prompt_version: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    latency_ms: float
    created: str  # UTC ISO timestamp of the API call

    def cost_usd(self) -> float:
        p = PRICES[self.model]
        scale = 1.0 if is_peak(datetime.fromisoformat(self.created)) else 0.5
        miss = self.input_tokens - self.cached_input_tokens
        usd = (
            self.cached_input_tokens * p["input_hit"]
            + miss * p["input_miss"]
            + self.output_tokens * p["output"]
        )
        return scale * usd / 1e6


def cache_key(model: str, prompt_version: str, text: str) -> str:
    return hashlib.sha1(f"{model}\x1f{prompt_version}\x1f{text}".encode()).hexdigest()


class TranslationCache:
    """Append-only JSONL of Translation records, keyed by model, prompt version and text."""

    def __init__(self, path: Path):
        self.path = path
        self._items: dict[str, Translation] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line:
                    t = Translation(**json.loads(line))
                    self._items[cache_key(t.model, t.prompt_version, t.source)] = t

    def get(self, model: str, prompt_version: str, text: str) -> Translation | None:
        return self._items.get(cache_key(model, prompt_version, text))

    def put(self, t: Translation) -> None:
        self._items[cache_key(t.model, t.prompt_version, t.source)] = t
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(asdict(t), ensure_ascii=False) + "\n")


class DeepSeekTranslator:
    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-flash",
        base_url: str = "https://api.deepseek.com",
        timeout: float = 60.0,
        retries: int = 4,
    ):
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set (add it to .env).")
        self.api_key, self.model, self.base_url = api_key, model, base_url.rstrip("/")
        self.timeout, self.retries = timeout, retries
        self.prompt_version = PROMPT_VERSION

    def _post(self, body: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"DeepSeek API error {e.code}: {detail}") from e
            except (urllib.error.URLError, TimeoutError):
                if attempt < self.retries:
                    time.sleep(2**attempt)
                    continue
                raise
        raise AssertionError("unreachable")

    def translate(self, text: str) -> Translation:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "thinking": {"type": "disabled"},
            "temperature": 0,
            "max_tokens": 300,
        }
        created = datetime.now(UTC).isoformat(timespec="seconds")
        t0 = time.perf_counter()
        data = self._post(body)
        latency_ms = 1000 * (time.perf_counter() - t0)
        usage = data.get("usage", {})
        out = data["choices"][0]["message"]["content"].strip()
        return Translation(
            source=text,
            text=" ".join(out.split()),
            model=self.model,
            prompt_version=self.prompt_version,
            input_tokens=usage.get("prompt_tokens", 0),
            cached_input_tokens=usage.get("prompt_cache_hit_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=round(latency_ms, 1),
            created=created,
        )


def translate_all(
    texts: list[str],
    cache: TranslationCache,
    model: str,
    prompt_version: str,
    make_translator: Callable[[], DeepSeekTranslator],
    workers: int = 8,
) -> tuple[list[str], list[Translation | None]]:
    """English text for every input, plus the Translation record (None if passed through).

    The translator is only built when something is missing from the cache, so cached runs
    need no API key.
    """
    todo = sorted(
        {t for t in texts if needs_translation(t) and not cache.get(model, prompt_version, t)}
    )
    if todo:
        translator = make_translator()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for t in pool.map(translator.translate, todo):
                cache.put(t)
    records = [cache.get(model, prompt_version, t) if needs_translation(t) else None for t in texts]
    return [r.text if r else t for r, t in zip(records, texts, strict=True)], records


def translation_stats(records: list[Translation | None]) -> dict:
    sent = [r for r in records if r]
    n = len(records)
    if not sent:
        return {"queries": n, "translated": 0}
    cost = sum(r.cost_usd() for r in sent)
    lat = sorted(r.latency_ms for r in sent)
    return {
        "queries": n,
        "translated": len(sent),
        "model": sent[0].model,
        "prompt_version": sent[0].prompt_version,
        "mean_input_tokens": round(sum(r.input_tokens for r in sent) / len(sent), 1),
        "mean_output_tokens": round(sum(r.output_tokens for r in sent) / len(sent), 1),
        "mean_latency_ms": round(sum(lat) / len(lat), 1),
        "p95_latency_ms": lat[min(len(lat) - 1, int(0.95 * len(lat)))],
        # Averaged over every query, English included, since English costs nothing.
        "usd_per_1k_queries": round(1000 * cost / n, 4),
        "mean_added_latency_ms": round(sum(lat) / n, 1),
    }
