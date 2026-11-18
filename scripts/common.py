"""market_news 스크립트 공용 상수·헬퍼."""
from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "newsletters"
TEMPLATE_DIR = BASE_DIR / "templates"

MARKETS = ("KR", "US", "GLOBAL")
IMPACTS = {
    "positive": {"label": "호재", "color": "#dc2626", "bg": "#fef2f2", "arrow": "▲"},
    "negative": {"label": "악재", "color": "#2563eb", "bg": "#eff6ff", "arrow": "▼"},
    "mixed":    {"label": "혼재", "color": "#b45309", "bg": "#fffbeb", "arrow": "◆"},
    "neutral":  {"label": "중립", "color": "#64748b", "bg": "#f1f5f9", "arrow": "●"},
}
HORIZONS = {"short": "단기", "mid": "중기", "long": "장기"}
REGIONS = {"KR": "🇰🇷 국내", "US": "🇺🇸 미국", "GLOBAL": "🌏 글로벌"}


def load_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def load_industries() -> dict:
    raw = load_json(CONFIG_DIR / "industries.json", {}) or {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def load_watchlist(industry: str | None) -> dict:
    raw = load_json(CONFIG_DIR / "watchlist.json", {}) or {}

    def applies(item: dict) -> bool:
        inds = item.get("industries") or []
        return not inds or (industry in inds)

    return {
        "tickers": [t for t in raw.get("tickers", []) if applies(t)],
        "keywords": [k for k in raw.get("keywords", []) if applies(k)],
    }


def ticker_key(t: dict) -> str:
    return f"{t.get('market', '')}:{str(t.get('code', '')).upper()}"


def quote_url(t: dict) -> str:
    market, code = t.get("market"), str(t.get("code", ""))
    if market == "KR":
        return f"https://finance.naver.com/item/main.naver?code={code}"
    return f"https://finance.yahoo.com/quote/{code}"


def subject_of(data_path: Path) -> str | None:
    parent = data_path.resolve().parent
    return None if parent == DATA_DIR.resolve() else parent.name
