#!/usr/bin/env python3
"""
데이터 JSON 검증. 오류(ERROR)가 하나라도 있으면 종료코드 1. 경고(WARN)는 참고.

사용법: python scripts/validate_data.py data/semiconductor/20261118_0630.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HORIZONS, IMPACTS, MARKETS, load_industries, load_json, subject_of  # noqa: E402

CODE_RE = {"KR": re.compile(r"^\d{6}$"), "US": re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$"),
           "GLOBAL": re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")}
REQ_ARTICLE = ("category", "title", "url", "summary", "source", "time", "region", "importance", "impact",
               "horizon", "insight")


def validate(path: Path) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return [f"JSON 파싱 실패: {e}"], []

    industry = data.get("industry") or subject_of(path)
    inds = load_industries()
    if industry not in inds:
        errs.append(f"industry '{industry}' 가 config/industries.json 에 없음")
    if subject_of(path) and industry != subject_of(path):
        errs.append(f"industry '{industry}' 와 폴더 '{subject_of(path)}' 가 다름")
    sig_keys = {f["key"] for f in inds.get(industry, {}).get("signal_fields", [])}

    try:
        pub = datetime.fromisoformat(data["published_at"])
        if path.stem != f"{pub:%Y%m%d_%H%M}":
            errs.append(f"파일명 {path.stem} 과 published_at {pub:%Y%m%d_%H%M} 불일치")
    except Exception:  # noqa: BLE001
        errs.append("published_at 누락/형식 오류(YYYY-MM-DDTHH:MM)")
        pub = None

    if pub:
        from datetime import timezone
        now_kst = datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None)
        if os.getenv("GITHUB_ACTIONS") != "true" and pub > now_kst + timedelta(minutes=5):
            errs.append(f"published_at {pub:%H:%M} 이 현재 시각({now_kst:%H:%M} KST)보다 미래임 — 실제 현재 시각을 쓸 것")
        recent = [p for p in path.parent.glob("2*.json") if p.name < path.name and p.stem >= f"{pub - timedelta(hours=2):%Y%m%d_%H%M}"]
        if recent:
            errs.append(f"2시간 안에 이미 발행한 호가 있음({recent[-1].name}) — 한 번 실행에 한 호만 발행")

    b = data.get("briefing") or []
    if not 3 <= len(b) <= 5:
        warns.append(f"briefing 은 3~5줄 권장(현재 {len(b)})")

    cats = {c["id"] for c in (load_json(path.parent / "categories.json", {}) or {}).get("categories", [])}
    arts = data.get("articles") or []
    if not arts:
        errs.append("articles 가 비어 있음")

    # 이전 2개 호 URL
    prev_urls = set()
    prev_files = sorted(p for p in path.parent.glob("2*.json") if p.name < path.name)[-2:]
    for pf in prev_files:
        prev_urls |= {a.get("url") for a in (load_json(pf, {}) or {}).get("articles", [])}

    seen = set()
    for i, a in enumerate(arts, 1):
        tag = f"기사{i}({str(a.get('title', ''))[:20]})"
        for k in REQ_ARTICLE:
            if a.get(k) in (None, ""):
                errs.append(f"{tag}: '{k}' 누락")
        if a.get("category") and a["category"] not in cats and not (a.get("category_label") and a.get("category_emoji")):
            errs.append(f"{tag}: 새 카테고리 '{a['category']}' 는 category_label/category_emoji 필요")
        if not str(a.get("url", "")).startswith(("http://", "https://")):
            errs.append(f"{tag}: url 형식 오류")
        if a.get("url") in seen:
            errs.append(f"{tag}: 중복 URL")
        seen.add(a.get("url"))
        if a.get("url") in prev_urls:
            warns.append(f"{tag}: 이전 호에 이미 실린 URL")
        if a.get("region") and a["region"] not in MARKETS:
            errs.append(f"{tag}: region 은 {MARKETS} 중 하나")
        if a.get("impact") and a["impact"] not in IMPACTS:
            errs.append(f"{tag}: impact 는 {list(IMPACTS)} 중 하나")
        if a.get("horizon") and a["horizon"] not in HORIZONS:
            errs.append(f"{tag}: horizon 은 {list(HORIZONS)} 중 하나")
        if a.get("importance") not in (1, 2, 3):
            errs.append(f"{tag}: importance 는 1|2|3")
        if len(str(a.get("summary", ""))) > 260:
            warns.append(f"{tag}: summary 가 깁니다({len(a['summary'])}자, 200자 권장)")
        if len(str(a.get("insight", ""))) > 170:
            warns.append(f"{tag}: insight 가 깁니다({len(a['insight'])}자, 120자 권장)")
        for k in (a.get("signals") or {}):
            if k not in sig_keys:
                errs.append(f"{tag}: signals 키 '{k}' 는 industries.json 의 {sorted(sig_keys)} 중 하나여야 함")
        for t in a.get("tickers") or []:
            m, c = t.get("market"), str(t.get("code", ""))
            if m not in MARKETS:
                errs.append(f"{tag}: 종목 {t.get('name')} market 오류")
            elif not CODE_RE[m].match(c):
                errs.append(f"{tag}: 종목 {t.get('name')} code '{c}' 형식 오류({m})")
            if not t.get("name"):
                errs.append(f"{tag}: 종목 name 누락")
            if t.get("effect") and t["effect"] not in IMPACTS:
                errs.append(f"{tag}: 종목 {t.get('name')} effect 오류")
        # 24시간 체크 (time = MM/DD HH:MM, KST)
        if pub and re.match(r"^\d{2}/\d{2} \d{2}:\d{2}$", str(a.get("time", ""))):
            t = datetime.strptime(f"{pub.year}/{a['time']}", "%Y/%m/%d %H:%M")
            if t > pub + timedelta(days=200):
                t = t.replace(year=pub.year - 1)
            if t < pub - timedelta(hours=26):
                errs.append(f"{tag}: 24시간보다 오래된 기사({a['time']})")
            elif t > pub + timedelta(minutes=30):
                warns.append(f"{tag}: 발행 시각보다 늦은 기사 시각({a['time']}) — KST 변환 확인")
        elif a.get("time"):
            errs.append(f"{tag}: time 형식은 'MM/DD HH:MM'")

    for e in data.get("events") or []:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(e.get("date", ""))):
            errs.append(f"일정 '{e.get('event')}': date 형식 YYYY-MM-DD")
    for m in data.get("market_snapshot") or []:
        if not m.get("source"):
            errs.append(f"시장지표 '{m.get('label')}': source 필요")
    for r in data.get("requests") or []:
        if not r.get("links"):
            warns.append(f"요청 '{str(r.get('request'))[:20]}': 근거 링크 없음")
    for f in data.get("filings") or []:
        if not str(f.get("url", "")).startswith("http"):
            errs.append(f"공시 '{f.get('title')}': url 필요")
    return errs, warns


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rc = 0
    for p in sys.argv[1:]:
        errs, warns = validate(Path(p))
        print(f"== {p}: 오류 {len(errs)} · 경고 {len(warns)}")
        for e in errs:
            print(f"  ERROR {e}")
        for w in warns:
            print(f"  WARN  {w}")
        rc |= bool(errs)
    return rc


if __name__ == "__main__":
    sys.exit(main())
