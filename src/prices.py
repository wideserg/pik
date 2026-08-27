"""Load, save, fetch, and diff Cursor model prices."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
PRICES_PATH = ROOT_DIR / "prices.json"
STATE_PATH = ROOT_DIR / "state.json"
DOCS_URL = "https://cursor.com/docs/models-and-pricing.md"

DEFAULT_ALIASES: dict[str, list[str]] = {
    "Grok 4.6": [
        "Cursor Grok 4.6",
        "Grok 4.6 High",
        "Grok 4.6 Medium",
        "Grok 4.6 Extra High",
    ],
    "Grok 4.6 (Fast)": ["Grok 4.6 Fast", "Cursor Grok 4.6 Fast"],
    "Grok 4.5": ["Cursor Grok 4.5", "Grok 4.5 High", "Grok 4.5 Medium"],
    "Grok 4.5 (Fast)": ["Grok 4.5 Fast", "Cursor Grok 4.5 Fast"],
    "Composer 2.5": ["Composer 2.5 High", "Composer 2.5 Medium"],
    "Composer 2.5 (Fast)": ["Composer 2.5 Fast"],
    "GPT-5.4": ["GPT-5.4 Medium", "GPT-5.4 High", "GPT 5.4"],
    "GPT-5.6 Sol": ["GPT-5.6 Sol Medium", "GPT-5.6 Sol High"],
    "GPT-5.6 Terra": ["GPT-5.6 Terra Medium", "GPT-5.6 Terra High"],
    "GPT-5.6 Luna": ["GPT-5.6 Luna Medium", "GPT-5.6 Luna High"],
    "Gemini 3.7 Flash": ["Gemini 3.7 Flash High", "Gemini 3.7 Flash Medium"],
    "Gemini 3.1 Pro": ["Gemini 3.1 Pro High", "Gemini 3.1 Pro Medium"],
    "GLM 5.2": ["GLM 5.2 High", "GLM 5.2 Medium"],
}

PRICE_FIELDS = ("input", "output", "cacheRead")


def money(s: str) -> float | None:
    s = s.strip()
    if s in ("-", "", "—"):
        return None
    return float(s.replace("$", "").replace(",", ""))


def strip_link(name: str) -> str:
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", name).strip()


def parse_models(markdown: str) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    seen: set[str] = set()

    for line in markdown.splitlines():
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 6:
            continue
        name, provider, inp, cw, cr, out = cols[:6]
        if name.lower() == "model" or set(name) <= {"-", ":"}:
            continue
        name = strip_link(name)
        if provider in ("Provider", "Price"):
            continue
        if not re.search(r"\$|\d", inp):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        models.append(
            {
                "name": name,
                "provider": provider,
                "input": money(inp),
                "cacheWrite": money(cw),
                "cacheRead": money(cr),
                "output": money(out),
                "pool": "cursor" if provider == "Cursor" else "other",
                "aliases": [],
            }
        )
    return models


def load_prices_file() -> dict[str, Any]:
    data = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
    return data


def load_models() -> list[dict[str, Any]]:
    return load_prices_file()["models"]


def save_prices_file(data: dict[str, Any]) -> None:
    PRICES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_existing_aliases() -> dict[str, list[str]]:
    if not PRICES_PATH.exists():
        return {}
    data = load_prices_file()
    return {m["name"]: m.get("aliases", []) for m in data.get("models", [])}


def apply_aliases(models: list[dict[str, Any]], existing: dict[str, list[str]]) -> None:
    for m in models:
        if m["name"] in existing:
            m["aliases"] = existing[m["name"]]
        else:
            m["aliases"] = DEFAULT_ALIASES.get(m["name"], [])


def fetch_markdown() -> str:
    req = urllib.request.Request(
        DOCS_URL,
        headers={"User-Agent": "pik-price-refresh/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def build_prices_payload(models: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source": "https://cursor.com/docs/models-and-pricing",
        "fetched": date.today().isoformat(),
        "unit": "USD per 1M tokens",
        "tokenRateOtherPool": 0.25,
        "models": models,
    }


def fetch_and_save_prices() -> dict[str, Any]:
    markdown = fetch_markdown()
    models = parse_models(markdown)
    existing = load_existing_aliases()
    apply_aliases(models, existing)
    payload = build_prices_payload(models)
    save_prices_file(payload)
    return payload


def _fmt_price(value: float | None) -> str:
    if value is None:
        return "—"
    if value == int(value):
        return f"${int(value)}"
    return f"${value:g}"


@dataclass
class PriceChange:
    name: str
    field: str
    old: float | None
    new: float | None

    def line(self) -> str:
        label = {"input": "in", "output": "out", "cacheRead": "cache"}.get(self.field, self.field)
        return f"{self.name}: {label} {_fmt_price(self.old)} → {_fmt_price(self.new)}"


@dataclass
class PriceDiff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[PriceChange] = field(default_factory=list)

    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def summary_lines(self, max_lines: int = 8) -> tuple[list[str], int]:
        lines: list[str] = []
        for name in self.added:
            lines.append(f"+ {name}")
        for name in self.removed:
            lines.append(f"− {name}")
        for change in self.changed:
            lines.append(change.line())
        extra = max(0, len(lines) - max_lines)
        return lines[:max_lines], extra


def diff_prices(old_models: list[dict[str, Any]], new_models: list[dict[str, Any]]) -> PriceDiff:
    old_by_name = {m["name"]: m for m in old_models}
    new_by_name = {m["name"]: m for m in new_models}

    added = sorted(name for name in new_by_name if name not in old_by_name)
    removed = sorted(name for name in old_by_name if name not in new_by_name)
    changed: list[PriceChange] = []

    for name in sorted(old_by_name.keys() & new_by_name.keys()):
        old_m = old_by_name[name]
        new_m = new_by_name[name]
        for fld in PRICE_FIELDS:
            if old_m.get(fld) != new_m.get(fld):
                changed.append(
                    PriceChange(
                        name=name,
                        field=fld,
                        old=old_m.get(fld),
                        new=new_m.get(fld),
                    )
                )

    return PriceDiff(added=added, removed=removed, changed=changed)


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"theme": "dark"}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass
class RefreshResult:
    models: list[dict[str, Any]]
    skipped: bool = False
    refreshed: bool = False
    fetch_failed: bool = False
    error: str | None = None
    diff: PriceDiff | None = None


def ensure_daily_refresh(state: dict[str, Any]) -> RefreshResult:
    today = date.today().isoformat()
    old_models: list[dict[str, Any]] = []

    try:
        current = load_prices_file()
        old_models = current.get("models", [])
    except (OSError, json.JSONDecodeError, KeyError):
        pass

    if state.get("lastFetch") == today and old_models:
        return RefreshResult(models=old_models, skipped=True)

    try:
        new_payload = fetch_and_save_prices()
        new_models = new_payload["models"]
        diff = diff_prices(old_models, new_models)
        state["lastFetch"] = today
        save_state(state)
        return RefreshResult(
            models=new_models,
            refreshed=True,
            diff=diff,
        )
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        return RefreshResult(
            models=old_models,
            fetch_failed=True,
            error=str(exc),
        )
