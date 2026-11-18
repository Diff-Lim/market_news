#!/usr/bin/env python3
"""
투자 브리핑 생성기: 데이터(JSON) + 템플릿(Jinja2) -> 뉴스레터 HTML (+ 메일 발송)

구조
  - UI       : templates/newsletter.html
  - 산업 설정 : config/industries.json   (제목·이모지·산업 특화 시그널 라벨)
  - 관심종목  : config/watchlist.json
  - 분류      : data/<산업>/categories.json   (새 카테고리 자동 누적)
  - 데이터    : data/<산업>/YYYYMMDD_HHMM.json (에이전트 작성 + enrich_data.py 가 enriched 추가)
  - 출력      : newsletters/<산업>/YYYYMMDD_HHMM.html

사용법
  python scripts/generate_newsletter.py data/semiconductor/20261118_0630.json
  python scripts/generate_newsletter.py data/semiconductor/20261118_0630.json -o /tmp/preview.html
  python scripts/generate_newsletter.py data/semiconductor/20261118_0630.json --send   # GitHub Actions 전용
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    HORIZONS, IMPACTS, OUTPUT_DIR, REGIONS, TEMPLATE_DIR,
    load_industries, load_json, load_watchlist, quote_url, subject_of, ticker_key,
)

DEFAULT_PALETTE = ["#db2777", "#0891b2", "#ca8a04", "#4f46e5", "#15803d", "#b91c1c", "#9333ea", "#0d9488"]
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
DISCLAIMER = ("본 브리핑은 공개된 뉴스·공시를 정리한 참고 자료이며 투자 권유가 아닙니다. "
              "호재/악재·영향 기간은 기사 내용에 대한 해석이고, 투자 판단과 그 결과의 책임은 투자자 본인에게 있습니다.")


# ---------- 카테고리 ----------
def load_registry(path: Path) -> tuple[list[dict], list[str]]:
    raw = load_json(path, {}) or {}
    return raw.get("categories") or [], raw.get("palette") or DEFAULT_PALETTE


def save_registry(path: Path, cats: list[dict], palette: list[str]) -> None:
    path.write_text(json.dumps({"palette": palette, "categories": cats}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def resolve_categories(articles: list[dict], path: Path) -> tuple[list[dict], dict]:
    registry, palette = load_registry(path)
    known = {c["id"]: c for c in registry}
    changed = False
    for a in articles:
        cid = a.get("category")
        if cid in known:
            continue
        if not (cid and a.get("category_label") and a.get("category_emoji")):
            raise ValueError(f"알 수 없는 카테고리 '{cid}' — category_label/category_emoji 필요 "
                             f"(기사: {str(a.get('title', '?'))[:40]})")
        cat = {"id": cid, "emoji": a["category_emoji"], "label": a["category_label"],
               "color": palette[len(registry) % len(palette)]}
        registry.append(cat)
        known[cid] = cat
        changed = True
    if changed:
        save_registry(path, registry, palette)
    return registry, known


# ---------- 날짜 ----------
def format_dates(published_at: str) -> dict:
    dt = datetime.fromisoformat(published_at)
    date_label = f"{dt.year}년 {dt.month}월 {dt.day}일"
    ampm = "오전" if dt.hour < 12 else "오후"
    time_label = f"{ampm} {dt.hour % 12 or 12}:{dt.minute:02d}"
    return {
        "dt": dt,
        "date_label": date_label,
        "meta_label": f"{date_label} ({WEEKDAYS_KO[dt.weekday()]}) {time_label}",
        "footer_label": f"{date_label} {time_label}",
    }


# ---------- 종목 ----------
def decorate_ticker(t: dict, quotes: dict) -> dict:
    q = quotes.get(ticker_key(t)) or {}
    eff = IMPACTS.get(t.get("effect") or "neutral", IMPACTS["neutral"])
    chg = q.get("change_pct")
    return {
        **t,
        "url": quote_url(t),
        "effect_style": eff,
        "change_label": (f"{chg:+.2f}%" if isinstance(chg, (int, float)) else ""),
        "change_color": ("#dc2626" if (chg or 0) > 0 else "#2563eb" if (chg or 0) < 0 else "#64748b"),
    }


def summarize_tickers(articles: list[dict], quotes: dict, watch_keys: set[str]) -> list[dict]:
    agg: dict[str, dict] = {}
    for a in articles:
        for t in a.get("tickers") or []:
            k = ticker_key(t)
            row = agg.setdefault(k, {"ticker": t, "count": 0, "pos": 0, "neg": 0, "max_imp": 0})
            row["count"] += 1
            row["pos"] += t.get("effect") == "positive"
            row["neg"] += t.get("effect") == "negative"
            row["max_imp"] = max(row["max_imp"], int(a.get("importance") or 1))
    rows = []
    for k, r in agg.items():
        net = "positive" if r["pos"] > r["neg"] else "negative" if r["neg"] > r["pos"] else (
            "mixed" if r["pos"] else "neutral")
        rows.append({**decorate_ticker({**r["ticker"], "effect": net}, quotes),
                     "count": r["count"], "pos": r["pos"], "neg": r["neg"],
                     "max_imp": r["max_imp"], "watched": k in watch_keys,
                     "region": REGIONS.get(r["ticker"].get("market"), "")})
    rows.sort(key=lambda r: (-r["watched"], -r["max_imp"], -r["count"], r.get("name", "")))
    return rows


def merge_filings(data: dict) -> list[dict]:
    seen, out = set(), []
    for f in (data.get("filings") or []) + ((data.get("enriched") or {}).get("filings") or []):
        url = f.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(f)
    out.sort(key=lambda f: (f.get("date", ""), f.get("name", "")), reverse=True)
    return out


# ---------- 컨텍스트 ----------
def build_context(data: dict, data_path: Path) -> dict:
    industry = data.get("industry") or subject_of(data_path) or ""
    ind_cfg = load_industries().get(industry, {})
    signal_labels = {f["key"]: f["label"] for f in ind_cfg.get("signal_fields", [])}
    quotes = (data.get("enriched") or {}).get("quotes") or {}
    watch = load_watchlist(industry)
    watch_keys = {ticker_key(t) for t in watch["tickers"]}

    articles = data.get("articles", [])
    registry, known = resolve_categories(articles, data_path.parent / "categories.json")

    decorated = []
    for a in articles:
        imp = IMPACTS.get(a.get("impact") or "neutral", IMPACTS["neutral"])
        sig = a.get("signals") or {}
        decorated.append({
            **a,
            "importance": int(a.get("importance") or 1),
            "impact_style": imp,
            "horizon_label": HORIZONS.get(a.get("horizon") or "", ""),
            "region_label": REGIONS.get(a.get("region") or "", ""),
            "ticker_chips": [decorate_ticker(t, quotes) for t in a.get("tickers") or []],
            "signal_items": [{"label": signal_labels.get(k, k), "value": v} for k, v in sig.items() if v],
            "cat": known[a["category"]],
        })

    grouped: dict[str, list] = {}
    for a in decorated:
        grouped.setdefault(a["category"], []).append(a)
    categories = []
    for cat in registry:
        arts = grouped.get(cat["id"])
        if arts:
            arts.sort(key=lambda x: -x["importance"])
            categories.append({**cat, "articles": arts})
    # 중요도 높은 기사가 많은 카테고리를 먼저
    categories.sort(key=lambda c: (-max(a["importance"] for a in c["articles"]), -len(c["articles"])))

    top = sorted([a for a in decorated if a["importance"] >= 3], key=lambda x: x["cat"]["id"])
    impact_counts = {k: sum(1 for a in decorated if (a.get("impact") or "neutral") == k) for k in IMPACTS}
    sources = data.get("sources", [])
    dates = format_dates(data["published_at"])
    enriched = data.get("enriched") or {}

    return {
        "industry": industry,
        "title": data.get("title") or ind_cfg.get("title") or "투자 브리핑",
        "emoji": data.get("emoji") or ind_cfg.get("emoji") or "📈",
        **{k: dates[k] for k in ("date_label", "meta_label", "footer_label")},
        "sources_label": " · ".join(sources),
        "total_articles": len(decorated),
        "source_count": len(sources),
        "top_count": len(top),
        "impact_counts": impact_counts,
        "impacts": IMPACTS,
        "briefing": data.get("briefing") or [],
        "top_articles": top,
        "market_snapshot": data.get("market_snapshot") or [],
        "ticker_rows": summarize_tickers(decorated, quotes, watch_keys),
        "quotes_as_of": enriched.get("quotes_as_of", ""),
        "watchlist_notes": data.get("watchlist_notes") or [],
        "events": sorted(data.get("events") or [], key=lambda e: e.get("date", "")),
        "filings": merge_filings(data),
        "requests": data.get("requests") or [],
        "categories": categories,
        "disclaimer": DISCLAIMER,
        "filename_stem": f"{dates['dt']:%Y%m%d_%H%M}",
    }


def render_html(ctx: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    return env.get_template("newsletter.html").render(**ctx)


def build_text(ctx: dict) -> str:
    lines = [f"{ctx['title']} | {ctx['footer_label']}", ""]
    if ctx["briefing"]:
        lines.append("[오늘의 투자 포인트]")
        lines += [f"- {b}" for b in ctx["briefing"]] + [""]
    for cat in ctx["categories"]:
        lines.append(f"[{cat['emoji']} {cat['label']}] {len(cat['articles'])}개")
        for a in cat["articles"]:
            tick = ", ".join(t.get("name", "") for t in a.get("tickers") or [])
            lines.append(f"- ({a['impact_style']['label']}) {a['title']}" + (f" / {tick}" if tick else ""))
            lines.append(f"  {a['url']}")
        lines.append("")
    lines += [ctx["sources_label"], "", ctx["disclaimer"]]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="데이터 JSON + 템플릿 -> 투자 브리핑 HTML")
    p.add_argument("data")
    p.add_argument("-o", "--output")
    p.add_argument("--send", action="store_true", help="생성 후 SMTP 발송 (GitHub Actions 에서만 사용)")
    args = p.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"오류: 데이터 파일 없음: {data_path}", file=sys.stderr)
        return 1
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ctx = build_context(data, data_path)
    html = render_html(ctx)

    subject = ctx["industry"] or subject_of(data_path)
    out = Path(args.output) if args.output else OUTPUT_DIR / (subject or "") / f"{ctx['filename_stem']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"생성 완료: {out} ({ctx['total_articles']}기사 · 핵심 {ctx['top_count']} · 종목 {len(ctx['ticker_rows'])})")

    if args.send:
        from email_sender import get_recipients, recipients_env, send_email
        recipients = get_recipients(subject)
        if not recipients:
            print(f"오류: {recipients_env(subject)} / RECIPIENTS 가 비어 있음", file=sys.stderr)
            return 1
        mail_subject = f"{ctx['emoji']} {ctx['title']} | {ctx['date_label']}"
        if ctx["briefing"]:
            mail_subject += f" — {ctx['briefing'][0][:40]}"
        text = build_text(ctx)
        print(f"발송 대상 {len(recipients)}명")
        ok = all(send_email(to, mail_subject, text, html, sender_name=ctx["title"]) for to in recipients)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
