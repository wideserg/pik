"""Pure matching logic — no Windows UI dependencies."""

import re
from difflib import SequenceMatcher

EFFORT_PATTERNS = [
    re.compile(r"\bextra\s+high\b", re.I),
    re.compile(r"\bhigh\b", re.I),
    re.compile(r"\bmedium\b", re.I),
    re.compile(r"\blow\b", re.I),
]


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    for pat in EFFORT_PATTERNS:
        text = pat.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_fast_model(model: dict) -> bool:
    name = normalize(model["name"])
    return "fast" in name or "(fast)" in model["name"].lower()


def _score_fuzzy(haystack: str, needle: str) -> float:
    if not needle:
        return 0.0
    ratio = SequenceMatcher(None, haystack, needle).ratio()
    h_tokens = set(haystack.split())
    n_tokens = set(needle.split())
    if n_tokens:
        overlap = len(h_tokens & n_tokens) / len(n_tokens)
        ratio = max(ratio, overlap * 0.9)
    return ratio


def match_model(haystack_parts: list[str], models: list[dict]) -> tuple[dict | None, str]:
    haystack = " ".join(p for p in haystack_parts if p and str(p).strip())
    normalized = normalize(haystack)
    has_fast = "fast" in normalized

    if not has_fast:
        candidates = [m for m in models if not _is_fast_model(m)]
    else:
        candidates = list(models)

    if not normalized:
        return None, haystack

    # 1. Exact alias or name match
    for m in candidates:
        if normalize(m["name"]) == normalized:
            return m, haystack
        for alias in m.get("aliases", []):
            if normalize(alias) == normalized:
                return m, haystack

    # 2. Substring: longest alias or name contained in haystack
    best_sub: dict | None = None
    best_len = 0
    for m in candidates:
        nm = normalize(m["name"])
        if nm and nm in normalized and len(nm) > best_len:
            best_sub = m
            best_len = len(nm)
        for alias in m.get("aliases", []):
            an = normalize(alias)
            if an and an in normalized and len(an) > best_len:
                best_sub = m
                best_len = len(an)
    if best_sub:
        return best_sub, haystack

    # 3. Fuzzy match
    best_score = 0.0
    best_m: dict | None = None
    min_score = 0.45

    for m in candidates:
        nm = normalize(m["name"])
        score = _score_fuzzy(normalized, nm)
        for alias in m.get("aliases", []):
            score = max(score, _score_fuzzy(normalized, normalize(alias)))
        if has_fast and _is_fast_model(m):
            score += 0.08
        if score > best_score:
            best_score = score
            best_m = m

    if best_m and best_score >= min_score:
        return best_m, haystack
    return None, haystack


def format_price_line(model: dict) -> tuple[str, str]:
    line1 = f"{model['name']}  {model['provider']}  {model['pool']}"
    parts: list[str] = []
    if model.get("input") is not None:
        parts.append(f"in ${model['input']}")
    if model.get("output") is not None:
        parts.append(f"out ${model['output']}")
    if model.get("cacheRead") is not None:
        parts.append(f"cache ${model['cacheRead']}")
    line2 = " / ".join(parts) + "   per 1M tok"
    return line1, line2


def format_card_fields(model: dict) -> dict:
    meta = f"{model['provider']} · {model['pool']}"
    price_parts: list[str] = []
    if model.get("input") is not None:
        price_parts.append(f"in ${model['input']}")
    if model.get("output") is not None:
        price_parts.append(f"out ${model['output']}")
    prices = "  /  ".join(price_parts)
    cache = None
    if model.get("cacheRead") is not None:
        cache = f"cache ${model['cacheRead']} · per 1M tok"
    elif prices:
        prices = f"{prices} · per 1M tok"
    return {
        "title": model["name"],
        "meta": meta,
        "prices": prices,
        "cache": cache,
        "hint": None,
    }
