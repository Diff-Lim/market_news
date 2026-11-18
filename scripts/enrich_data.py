#!/usr/bin/env python3
"""
데이터 JSON 보강: 기사에 언급된 종목 + 관심종목의 최근 공시와 직전 거래일 등락률을 붙임.
GitHub Actions 에서 실행(외부 API 접근 가능). 표준 라이브러리만 사용. 실패해도 뉴스레터 생성은 계속됨.

  - 국내 공시 : OpenDART API (환경 변수 DART_API_KEY 필요. https://opendart.fss.or.kr 에서 무료 발급)
  - 미국 공시 : SEC EDGAR (환경 변수 SEC_USER_AGENT 권장. 예: "market_news you@example.com")
  - 시세      : Yahoo Finance chart API (비공식. ENRICH_QUOTES=0 이면 끔)

결과는 데이터 JSON 의 "enriched" 키에 저장:
  {"at": ISO시각, "filings": [...], "quotes": {"KR:005930": {...}}, "quotes_as_of": "...", "notes": [...]}

사용법: python scripts/enrich_data.py data/semiconductor/20261118_0630.json [--days 3]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BASE_DIR, load_watchlist, subject_of, ticker_key  # noqa: E402

KST = timezone(timedelta(hours=9))
CACHE_DIR = BASE_DIR / ".cache"
SEC_FORMS = {"8-K", "8-K/A", "10-Q", "10-K", "6-K", "20-F", "S-1", "S-3", "SC 13D", "SC 13D/A", "DEF 14A"}
SEC_FORM_KO = {"8-K": "주요사항보고(8-K)", "10-Q": "분기보고서(10-Q)", "10-K": "연간보고서(10-K)",
               "6-K": "해외기업 수시보고(6-K)", "20-F": "해외기업 연간보고(20-F)", "S-1": "증권신고(S-1)",
               "S-3": "증권신고(S-3)", "SC 13D": "대량보유(13D)", "DEF 14A": "주총 위임장(DEF 14A)"}
MAX_PER_COMPANY = 5


def http_get(url: str, headers: dict | None = None, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0 market_news"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------- DART ----------------
def dart_corp_map(key: str, fetch=http_get) -> dict[str, str]:
    """종목코드(6자리) -> DART corp_code. 하루 단위로 캐시."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache = CACHE_DIR / "dart_corp_map.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        return json.loads(cache.read_text())
    raw = fetch(f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={key}")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read(z.namelist()[0])
    mapping = {}
    for el in ET.fromstring(xml).iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc:
            mapping[sc] = el.findtext("corp_code").strip()
    cache.write_text(json.dumps(mapping))
    return mapping


def dart_filings(tickers: list[dict], start: datetime, end: datetime, notes: list, fetch=http_get) -> list[dict]:
    key = os.getenv("DART_API_KEY", "").strip()
    if not key:
        notes.append("DART_API_KEY 없음 → 국내 공시 보강 생략")
        return []
    try:
        cmap = dart_corp_map(key, fetch)
    except Exception as e:  # noqa: BLE001
        notes.append(f"DART 기업코드 조회 실패: {e}")
        return []
    out = []
    for t in tickers:
        corp = cmap.get(str(t["code"]))
        if not corp:
            notes.append(f"DART 기업코드 없음(종목코드 확인 필요): {t.get('name')} {t['code']}")
            continue
        q = urllib.parse.urlencode({"crtfc_key": key, "corp_code": corp, "bgn_de": f"{start:%Y%m%d}",
                                    "end_de": f"{end:%Y%m%d}", "page_count": 20})
        try:
            res = json.loads(fetch(f"https://opendart.fss.or.kr/api/list.json?{q}"))
        except Exception as e:  # noqa: BLE001
            notes.append(f"DART 조회 실패 {t.get('name')}: {e}")
            continue
        if res.get("status") not in ("000", "013"):  # 013 = 조회 결과 없음
            notes.append(f"DART 응답 {res.get('status')} {res.get('message')} ({t.get('name')})")
            continue
        for item in (res.get("list") or [])[:MAX_PER_COMPANY]:
            d = item.get("rcept_dt", "")
            out.append({
                "market": "KR", "code": t["code"], "name": item.get("corp_name") or t.get("name"),
                "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d,
                "title": (item.get("report_nm") or "").strip(),
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('rcept_no')}",
                "auto": True,
            })
    return out


# ---------------- SEC ----------------
def sec_headers() -> dict:
    return {"User-Agent": os.getenv("SEC_USER_AGENT") or "market_news research contact@example.com",
            "Accept-Encoding": "identity"}


def sec_filings(tickers: list[dict], start: datetime, notes: list, fetch=http_get) -> list[dict]:
    if not tickers:
        return []
    try:
        table = json.loads(fetch("https://www.sec.gov/files/company_tickers.json", sec_headers()))
        cik_of = {v["ticker"].upper(): int(v["cik_str"]) for v in table.values()}
    except Exception as e:  # noqa: BLE001
        notes.append(f"SEC 티커표 조회 실패: {e}")
        return []
    out = []
    for t in tickers:
        sym = str(t["code"]).upper()
        cik = cik_of.get(sym) or cik_of.get(sym.replace(".", "-"))
        if not cik:
            continue  # SEC 비등록(해외 현지 상장 등)은 조용히 건너뜀
        try:
            sub = json.loads(fetch(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", sec_headers()))
        except Exception as e:  # noqa: BLE001
            notes.append(f"SEC 조회 실패 {sym}: {e}")
            continue
        r = sub.get("filings", {}).get("recent", {})
        n = 0
        for form, date, acc, doc, desc in zip(r.get("form", []), r.get("filingDate", []),
                                              r.get("accessionNumber", []), r.get("primaryDocument", []),
                                              r.get("primaryDocDescription", [])):
            if date < f"{start:%Y-%m-%d}":
                break  # 최신순 정렬
            if form not in SEC_FORMS:
                continue
            title = SEC_FORM_KO.get(form, form) + (f" — {desc}" if desc and desc.upper() != form else "")
            out.append({"market": "US", "code": sym, "name": t.get("name") or sub.get("name"), "date": date,
                        "title": title,
                        "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}",
                        "auto": True})
            n += 1
            if n >= MAX_PER_COMPANY:
                break
        time.sleep(0.15)  # SEC 초당 10회 제한 준수
    return out


# ---------------- 시세 ----------------
def yahoo_symbols(t: dict) -> list[str]:
    if t["market"] == "KR":
        return [f"{t['code']}.KS", f"{t['code']}.KQ"]
    return [str(t["code"])]


def fetch_quote(t: dict, fetch=http_get) -> dict | None:
    for sym in yahoo_symbols(t):
        try:
            res = json.loads(fetch(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
                                   f"?range=5d&interval=1d"))
            chart = res["chart"]["result"][0]
            closes = [c for c in chart["indicators"]["quote"][0]["close"] if c is not None]
            ts = chart.get("timestamp") or []
            if len(closes) < 2:
                continue
            last, prev = closes[-1], closes[-2]
            return {"symbol": sym, "close": round(last, 2), "change_pct": round((last / prev - 1) * 100, 2),
                    "currency": chart["meta"].get("currency"),
                    "date": datetime.fromtimestamp(ts[-1], KST).strftime("%m/%d") if ts else ""}
        except Exception:  # noqa: BLE001
            continue
    return None


# ---------------- main ----------------
def collect_tickers(data: dict, industry: str | None) -> list[dict]:
    seen, out = set(), []
    pool = [t for a in data.get("articles", []) for t in a.get("tickers") or []]
    pool += load_watchlist(industry)["tickers"]
    for t in pool:
        if not t.get("market") or not t.get("code"):
            continue
        k = ticker_key(t)
        if k not in seen:
            seen.add(k)
            out.append({"market": t["market"], "code": str(t["code"]).upper() if t["market"] != "KR" else str(t["code"]),
                        "name": t.get("name")})
    return out


def enrich(data: dict, industry: str | None, days: int = 3, fetch=http_get) -> dict:
    notes: list[str] = []
    end = datetime.fromisoformat(data["published_at"])
    start = end - timedelta(days=days)
    tickers = collect_tickers(data, industry)
    kr = [t for t in tickers if t["market"] == "KR"]
    us_like = [t for t in tickers if t["market"] in ("US", "GLOBAL")]

    filings = dart_filings(kr, start, end, notes, fetch) + sec_filings(us_like, start, notes, fetch)

    quotes = {}
    if os.getenv("ENRICH_QUOTES", "1") != "0":
        for t in tickers:
            q = fetch_quote(t, fetch)
            if q:
                quotes[ticker_key(t)] = q
        if tickers and not quotes:
            notes.append("시세 조회 실패(전체) → 등락률 생략")

    as_of = sorted({q["date"] for q in quotes.values() if q.get("date")})
    return {"at": datetime.now(KST).isoformat(timespec="minutes"), "filings": filings, "quotes": quotes,
            "quotes_as_of": as_of[-1] if as_of else "", "notes": notes}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("data")
    p.add_argument("--days", type=int, default=3, help="공시 조회 기간(발행일 기준 이전 N일)")
    args = p.parse_args()
    path = Path(args.data)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["enriched"] = enrich(data, data.get("industry") or subject_of(path), args.days)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    e = data["enriched"]
    print(f"보강 완료: 공시 {len(e['filings'])}건 · 시세 {len(e['quotes'])}종목")
    for n in e["notes"]:
        print(f"  - {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
