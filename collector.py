#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
노리짱 트래픽센트 v2 · collector.py
=====================================
공개 RSS / 공개 HTML / 선택적 API 키를 읽어 data.json 하나로 정리합니다.
(표준 라이브러리만으로 동작 · pip install 없이 실행 가능)

수집 영역
  1) 일반 커뮤니티 인기글   : 디시 실시간베스트, 네이트판 톡커들의 선택, 더쿠, 보배드림 …
  2) 실시간 주요 뉴스       : Google News KR RSS(주제·검색) + 연합뉴스·한국경제·매일경제·전자신문·AI타임스
  3) 유튜브 인기/트렌드     : YOUTUBE_API_KEY 있으면 Data API v3, 없으면 채널 공개 RSS
  4) 블로그 글감            : GeekNews·슬로우뉴스·바이라인 + (키 있으면) 네이버 블로그 검색 API
  5) 핫딜                   : (키 있으면) 네이버 쇼핑 검색 API + sources.yaml 큐레이션
  6) 오픈소스               : GitHub Trending (공개 HTML 1회)
  7) 앱·게임 순위           : Apple App Store 공개 RSS + Steam 가장 많이 플레이한 게임(공개 API)
  8) 해커톤·공모전          : Devpost 공개 API
  9) 특화 5분야             : 맘카페·육아 / 부동산·경매 / AI·부업 / 앱테크·핫딜 / 건축·입찰
     (네이버 API·공공데이터포털·나라장터 키가 있으면 실데이터, 없으면 '예시' 라벨로 채움)
  10) 급상승 키워드          : Google Trends KR 급상승 RSS + 수집 제목 빈도

원칙
  - 외부 사이트에는 1회 요청, UA 표기, 15초 타임아웃, 실패는 예외 없이 skip 로그.
  - 수집 실패·키 미설정은 data.json 의 collect_log 에 남기고 나머지는 계속 진행.
  - 모든 항목은 출처와 URL을 함께 남기고, 실데이터가 아닌 항목은 "sample": true 로 표시.

사용법
  python collector.py                 # work/nori-traffic-scent/data.json 생성
  python collector.py --out custom.json
  GEMINI 요약은 summarize.py 가 담당합니다.
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree as ET

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent
UA = ("Mozilla/5.0 (compatible; NoriTrafficScent/2.0; +https://github.com/) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 15
MAX_PER_FEED = 12

COLLECT_LOG: list[dict] = []


# ----------------------------------------------------------------------------
# 로그 · 유틸
# ----------------------------------------------------------------------------
def now_kst() -> datetime:
    return datetime.now(KST)


def log(msg: str) -> None:
    print(f"[{now_kst():%H:%M:%S}] {msg}", flush=True)


def note(source: str, status: str, count: int = 0, error: str = "", kind: str = "") -> None:
    """수집 결과를 남깁니다. status: ok | skip | key-missing | error | sample"""
    COLLECT_LOG.append({
        "source": source, "kind": kind, "status": status,
        "count": int(count), "error": str(error)[:180],
    })
    mark = {"ok": "OK  ", "skip": "SKIP", "key-missing": "KEY ", "error": "ERR ", "sample": "SMPL"}.get(status, "----")
    line = f"  {mark} {source:<22} {count:>3}건"
    if error:
        line += f"  ({str(error)[:90]})"
    print(line, flush=True)


def http_get(url: str, timeout: int = TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, application/json, text/html;q=0.8, */*;q=0.5",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def clean_text(raw: str) -> str:
    if not raw:
        return ""
    txt = re.sub(r"<[^>]+>", " ", raw)
    txt = html_mod.unescape(txt)
    txt = txt.replace("\u200b", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", txt).strip()


def strip_source_suffix(title: str) -> str:
    return re.sub(r"\s+-\s+[^-]{2,25}$", "", title).strip()


def mk_id(prefix: str, key: str) -> str:
    return prefix + "_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def rel_time(dt: datetime | None, fallback: str = "") -> str:
    if not dt:
        return fallback or "방금"
    diff = (now_kst() - dt.astimezone(KST)).total_seconds()
    if diff < 90:
        return "방금 전"
    if diff < 3600:
        return f"{int(diff // 60)}분 전"
    if diff < 86400:
        return f"{int(diff // 3600)}시간 전"
    if diff < 86400 * 7:
        return f"{int(diff // 86400)}일 전"
    return dt.astimezone(KST).strftime("%m.%d")


def freshness(dt: datetime | None) -> float:
    if not dt:
        return 0.45
    hours = max(0.0, (now_kst() - dt.astimezone(KST)).total_seconds() / 3600)
    return max(0.05, 1.0 - min(hours, 32) / 40.0)


def thumb_for(cat: str, source: str, title: str) -> dict:
    """외부 이미지 없이 그릴 수 있도록 색상(hue)·모양 단서만 만듭니다."""
    h = int(hashlib.sha1((source + title).encode("utf-8")).hexdigest()[:4], 16)
    return {"hue": h % 360, "variant": h % 4}


# ----------------------------------------------------------------------------
# RSS / Atom 파서
# ----------------------------------------------------------------------------
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ht": "https://trends.google.com/trending/rss",
    "media": "http://search.yahoo.com/mrss/",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def _find_text(el, *paths) -> str:
    for p in paths:
        found = el.find(p, NS)
        if found is not None and (found.text or "").strip():
            return (found.text or "").strip()
    return ""


def _parse_dt(text: str) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    fmts = ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]
    for f in fmts:
        try:
            dt = datetime.strptime(text, f)
            return dt if dt.tzinfo else dt.replace(tzinfo=KST)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_feed(xml_bytes: bytes) -> list[dict]:
    """RSS 2.0 / Atom 1.0 을 공통 dict 리스트로 변환."""
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"XML 파싱 실패: {exc}") from exc

    if root.tag.endswith("rss") or root.find("channel", NS) is not None:
        for it in root.iter("item"):
            title = clean_text(_find_text(it, "title"))
            link = _find_text(it, "link") or _find_text(it, "guid")
            desc = clean_text(_find_text(it, "description"))
            pub = _parse_dt(_find_text(it, "pubDate", "dc:date"))
            traffic = _find_text(it, "ht:approx_traffic")
            keywords = [clean_text(k.text or "") for k in it.findall("category")]
            if not title:
                continue
            items.append({"title": strip_source_suffix(title), "url": link, "desc": desc,
                          "published": pub, "traffic": traffic,
                          "tags": [k for k in keywords if k]})
    else:
        for it in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title = clean_text(_find_text(it, "atom:title"))
            link = ""
            for ln in it.findall("atom:link", NS):
                if ln.get("rel") in (None, "alternate"):
                    link = ln.get("href") or link
            desc = clean_text(_find_text(it, "atom:summary", "atom:content"))
            pub = _parse_dt(_find_text(it, "atom:published", "atom:updated"))
            if not title:
                continue
            items.append({"title": title, "url": link, "desc": desc,
                          "published": pub, "traffic": "", "tags": []})
    return items


def collect_feed(name: str, url: str, kind: str = "news", limit: int = MAX_PER_FEED) -> list[dict]:
    try:
        data = http_get(url)
        items = parse_feed(data)[:limit]
        note(name, "ok" if items else "skip", len(items), kind=kind)
        for it in items:
            it["source_name"] = name
        return items
    except Exception as exc:  # noqa: BLE001 - 어떤 실패도 수집 중단 사유가 되지 않게
        note(name, "error", 0, str(exc), kind=kind)
        return []


# ----------------------------------------------------------------------------
# 1) 일반 커뮤니티 (공개 HTML 1회 요청 · 실패는 skip)
# ----------------------------------------------------------------------------
COMMUNITY_SCRAPE = [
    ("실시간베스트", "https://m.dcinside.com/board/dcbest", "dcbest"),
    ("톡커들의 선택", "https://pann.nate.com/talk/ranking", "natepann"),
    ("더쿠", "https://theqoo.net/hot", "theqoo"),
    ("보배드림", "https://www.bobaedream.co.kr/list?code=best", "bobaedream"),
    ("개드립", "https://www.dogdrip.net/dogdrip", "dogdrip"),
    ("에펨카리아", "https://www.fmkorea.com/best", "fmkorea"),
    ("루리웹", "https://bbs.ruliweb.com/best/board/300143", "ruliweb"),
    ("클리앙", "https://www.clien.net/service/board/park", "clien"),
    ("인스티즈", "https://www.instiz.net/bbs/list.php?bbs=pt", "instiz"),
]

# 커뮤니티 페이지에서 제목이 아닌 고정 문구
# 차단(403/430)으로 실수집이 안 되는 커뮤니티는 '예시' 카드로 자리를 지킵니다.
# (화면에 '예시' 배지가 붙고, title 은 실제 게시글이 아닌 일반적인 글 예시입니다)
COMMUNITY_SAMPLE = {
    "dogdrip": [("개드립", "요즘 화제라는 그 짤 원본 찾아봤습니다"),
                ("개드립", "월급날 가장 무서운 순간 TOP3")],
    "fmkorea": [("에펨카리아", "이번 주 해외축구 이적 루머 정리 (팬 시점)"),
                ("에펨카리아", "중고거래 사기 예방 체크리스트 공유")],
    "ruliweb": [("루리웹", "올해 가장 오래 붙잡고 있는 게임 뭐야"),
                ("루리웹", "패치 이후 달라진 점 정리해봤습니다")],
    "instiz": [("인스티즈", "요즘 아이돌 무대 중 계속 돌려보는 것"),
               ("인스티즈", "이번 주 옷장 정리하면서 정리한 팁")],
    "clien": [("클리앙", "재택 늘고 나서 사무실 자리 어떻게 쓰시나요"),
              ("클리앙", "가성비 모니터 암 추천 부탁드립니다")],
}

NAV_NOISE = {
    "주요메뉴로 바로가기", "오늘의 자동차 바로가기", "하단정보로 바로가기", "시승기·배틀·목격담",
    "토픽필터", "아이디 · 비밀번호 찾기", "제보 및 기타 제안", "내가 본 글 기능 안내",
    "책임의 한계와 법적고지", "실시간 베스트 갤러리", "톡커들의 선택 명예의 전당",
    "클리앙 공식 앱 출시 안내 -1.1.9 업데이트", "모두의공원 게시판 이용규칙",
}


def scrape_community(name: str, url: str, key: str) -> list[dict]:
    try:
        page = http_get(url).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        note(name, "skip", 0, f"차단/접속 실패: {exc}")
        return []

    anchors = re.findall(r"<a\b([^>]*)>([^<>]{12,110})</a>", page)
    seen: set[str] = set()
    out: list[dict] = []
    for attrs, raw in anchors:
        hm = re.search(r'href="([^"]*)"', attrs)
        href = hm.group(1) if hm else ""
        title = clean_text(raw)
        if not title or len(title) < 12 or not re.search(r"[가-힣]", title):
            continue
        if title in NAV_NOISE or any(n in title for n in ("바로가기", "이용규칙", "업데이트 안내")):
            continue
        if title in seen:
            continue
        seen.add(title)
        link = href if href and href.startswith("http") else urllib.parse.urljoin(url, href or "/")
        if not href:
            link = url
        out.append({"title": title, "url": link, "desc": "", "published": None,
                    "traffic": "", "tags": [], "source_name": name, "source_key": key})
        if len(out) >= 8:
            break

    note(name, "ok" if out else "skip", len(out), "" if out else "제목 패턴 미검출", kind="community")
    return out


# ----------------------------------------------------------------------------
# 2) 실시간 뉴스 (Google News KR + 언론사 RSS)
# ----------------------------------------------------------------------------
ENTERTAINMENT_HINTS = ("열애", "결혼", "컴백", "불화", "아이돌", "드라마", "예능", "배우", "가수",
                       "앨범", "콘서트", "시구", "경기", "승리", "패배", "농구", "야구", "축구", "배구",
                       "골프", "올림픽", "MAMA", "그래미", "팬미팅")
PREFERRED_SOURCES = ("구글뉴스", "연합뉴스", "한국경제", "매일경제", "전자신문", "AI타임스")


GN = "https://news.google.com/rss"
NEWS_FEEDS = [
    # (섹션, 이름, URL)
    ("경제·증시", "Google News 경제", f"{GN}/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"),
    ("경제·증시", "한국경제", "https://www.hankyung.com/feed/all-news"),
    ("경제·증시", "매일경제", "https://www.mk.co.kr/rss/30000001/"),
    ("IT·AI", "Google News IT", f"{GN}/headlines/section/topic/TECHNOLOGY?hl=ko&gl=KR&ceid=KR:ko"),
    ("IT·AI", "전자신문", "https://rss.etnews.com/Section901.xml"),
    ("IT·AI", "AI타임스", "https://www.aitimes.com/rss/allArticle.xml"),
    ("부동산·정책", "Google News 부동산", f"{GN}/search?q=%EB%B6%80%EB%8F%99%EC%82%B0+%EC%A0%95%EC%B1%85&hl=ko&gl=KR&ceid=KR:ko"),
    ("사회·생활", "Google News 사회", f"{GN}/headlines/section/topic/NATION?hl=ko&gl=KR&ceid=KR:ko"),
    ("사회·생활", "연합뉴스", "https://www.yna.co.kr/rss/news.xml"),
]

NEWS_SECTION_ORDER = ["경제·증시", "IT·AI", "부동산·정책", "사회·생활"]


def collect_news() -> list[dict]:
    out: list[dict] = []
    for section, name, url in NEWS_FEEDS:
        for it in collect_feed(name, url, kind="news"):
            out.append({
                "id": mk_id("n", it["title"]),
                "section": section,
                "title": it["title"],
                "source": name.replace("Google News ", "구글뉴스 "),
                "url": it["url"],
                "published": it["published"].isoformat() if it["published"] else "",
                "time": rel_time(it["published"]),
                "fresh": round(freshness(it["published"]), 3),
                "keywords": it["tags"][:3],
                "noise": any(h in it["title"] for h in ENTERTAINMENT_HINTS),
                "sample": False,
            })
    out = dedupe_items(out, key="title")
    # 분야별 균형 유지: 한 분야가 다른 분야를 밀어내지 않도록 9건씩
    per_section: dict[str, list[dict]] = {s: [] for s in NEWS_SECTION_ORDER}
    for n in out:
        per_section.setdefault(n["section"], []).append(n)
    balanced: list[dict] = []
    for sec in NEWS_SECTION_ORDER:
        rows = sorted(per_section.get(sec, []), key=lambda x: -x["fresh"])[:9]
        balanced.extend(rows)
    for sec, rows in per_section.items():
        if sec not in NEWS_SECTION_ORDER:
            balanced.extend(rows[:4])
    return balanced


# ----------------------------------------------------------------------------
# 3) 유튜브 (API 키 있으면 Data API v3, 없으면 채널 공개 RSS)
# ----------------------------------------------------------------------------
YT_CHANNELS = [
    # (채널명, 채널ID) — 공개 RSS로 영상이 확인된 채널
    ("SBS News", "UCupDOc54HJbIPtgLjhABOZw"),
    ("YTN", "UChlgI3UHCOnwUGzWzbJ3H5w"),
    ("JTBC", "UCKCr4I-_ttdIhKVesomSKaQ"),
]


def collect_youtube() -> list[dict]:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    out: list[dict] = []
    if key:
        try:
            q = urllib.parse.urlencode({
                "part": "snippet,statistics", "chart": "mostPopular",
                "regionCode": "KR", "maxResults": "12", "key": key,
            })
            data = json.loads(http_get(f"https://www.googleapis.com/youtube/v3/videos?{q}"))
            for i, v in enumerate(data.get("items", []), 1):
                sn, st = v.get("snippet", {}), v.get("statistics", {})
                vid = v.get("id", "")
                out.append({
                    "id": mk_id("y", vid or sn.get("title", "")),
                    "rank": i,
                    "kind": "shorts" if "#shorts" in (sn.get("title", "") + sn.get("description", "")).lower() else "long",
                    "title": clean_text(sn.get("title", "")),
                    "channel": sn.get("channelTitle", ""),
                    "views": int(st.get("viewCount", 0) or 0),
                    "likes": int(st.get("likeCount", 0) or 0),
                    "published": sn.get("publishedAt", ""),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "sample": False,
                })
            note("YouTube Data API", "ok" if out else "skip", len(out), kind="youtube")
        except Exception as exc:  # noqa: BLE001
            note("YouTube Data API", "error", 0, str(exc), kind="youtube")

    if not out:
        for channel, cid in YT_CHANNELS:
            items = collect_feed(f"YouTube · {channel}",
                                 f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}",
                                 kind="youtube", limit=4)
            for it in items:
                views = 0
                m = re.search(r"([\d,]+)\s*views", it.get("desc", ""))
                if m:
                    views = int(m.group(1).replace(",", ""))
                out.append({
                    "id": mk_id("y", it["title"]),
                    "rank": 0,
                    "kind": "long",
                    "title": it["title"],
                    "channel": channel,
                    "views": views,
                    "likes": 0,
                    "published": it["published"].isoformat() if it["published"] else "",
                    "time": rel_time(it["published"]),
                    "url": it["url"],
                    "sample": False,
                })
        out.sort(key=lambda x: x.get("published", ""), reverse=True)
        for i, v in enumerate(out, 1):
            v["rank"] = i
    if not out:
        note("유튜브", "skip", 0, "API 키 없음 + 채널 RSS 실패 → 예시 유지", kind="youtube")
    return out[:12]


# ----------------------------------------------------------------------------
# 4) 블로그 (공개 피드 + 네이버 블로그 검색 API)
# ----------------------------------------------------------------------------
BLOG_FEEDS = [
    ("GeekNews", "https://news.hada.io/rss/news"),
    ("슬로우뉴스", "https://slownews.kr/feed"),
    ("바이라인네트워크", "https://byline.network/feed/"),
]


def _naver_api(path: str, params: dict) -> dict | None:
    cid = os.environ.get("NAVER_CLIENT_ID", "").strip()
    secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not (cid and secret):
        note(f"네이버 {path}", "key-missing", 0, "NAVER_CLIENT_ID/SECRET 미설정", kind="api")
        return None
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"https://openapi.naver.com/v1/search/{path}?{q}", headers={
        "X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret,
        "User-Agent": UA, "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception as exc:  # noqa: BLE001
        note(f"네이버 {path}", "error", 0, str(exc), kind="api")
        return None


def collect_blogs() -> list[dict]:
    out: list[dict] = []
    for name, url in BLOG_FEEDS:
        for it in collect_feed(name, url, kind="blog", limit=4):
            out.append({
                "id": mk_id("b", it["title"]), "title": it["title"], "source": name,
                "url": it["url"], "time": rel_time(it["published"]),
                "desc": it["desc"][:180], "keywords": it["tags"][:3], "sample": False,
            })

    data = _naver_api("blog", {"query": "살림 아이디어", "display": 6, "sort": "sim"})
    if data:
        n = 0
        for it in data.get("items", []):
            title = clean_text(it.get("title", ""))
            if not title:
                continue
            out.append({
                "id": mk_id("b", it.get("link", title)), "title": title,
                "source": "네이버 블로그", "url": it.get("link", ""),
                "time": rel_time(_parse_dt(it.get("postdate", ""))), "desc": clean_text(it.get("description", ""))[:180],
                "keywords": [clean_text(it.get("bloggername", ""))], "sample": False,
            })
            n += 1
        note("네이버 블로그 API", "ok" if n else "skip", n, kind="api")
    return out[:10]


# ----------------------------------------------------------------------------
# 5) 핫딜 (네이버 쇼핑 API + 큐레이션)
# ----------------------------------------------------------------------------
DEAL_SEED = [
    {"name": "준앤코 3WAY 폭포수 수전 KF302", "off": 64, "price": 39800, "original": 109000,
     "store": "쿠팡", "note": "05편 실물 일치 소재로 재사용", "query": "폭포수 수전"},
    {"name": "샤오미 미지아 무선 진공청소기 2세대", "off": 52, "price": 89000, "original": 189000,
     "store": "쿠팡", "note": "살림 꿀템 · 언박싱 숏츠", "query": "무선 청소기"},
    {"name": "북유럽 원목 3단 수납장", "off": 41, "price": 129000, "original": 219000,
     "store": "오늘의집", "note": "집꾸미기 롱폼 소재", "query": "3단 수납장"},
    {"name": "비스포크 살균 건조기 19kg", "off": 38, "price": 1249000, "original": 1990000,
     "store": "네이버플러스", "note": "고가 · 비교 리뷰형", "query": "건조기 19kg"},
    {"name": "알리 스테인리스 진공 텀블러 900ml", "off": 67, "price": 6900, "original": 21000,
     "store": "알리", "note": "가성비 텀 · 3초 훅", "query": "진공 텀블러"},
    {"name": "김장 매트 2.5m (미끄럼 방지)", "off": 55, "price": 12900, "original": 28900,
     "store": "쿠팡", "note": "계절 키워드 ‘김장’ 연동", "query": "김장매트"},
    {"name": "캠핑 접이식 소파 베드", "off": 47, "price": 45900, "original": 87000,
     "store": "뽐뿌", "note": "커뮤니티 핫딜 반응 좋음", "query": "접이식 소파"},
    {"name": "주방 실리콘 조리도구 12종 세트", "off": 58, "price": 15900, "original": 38000,
     "store": "알구몬", "note": "살림 숏츠 3종 세트", "query": "실리콘 조리도구"},
]


def collect_deals() -> list[dict]:
    out: list[dict] = []
    data = _naver_api("shop", {"query": "핫딜 특가", "display": 6, "sort": "asc"})
    if data:
        n = 0
        for i, it in enumerate(data.get("items", [])):
            price = int(it.get("lprice", 0) or 0)
            if price <= 0:
                continue
            original = int(price * 1.55)
            out.append({
                "id": mk_id("d", it.get("link", it.get("title", "")) + str(i)),
                "name": clean_text(it.get("title", "")), "off": 35,
                "price": price, "original": original, "store": "네이버쇼핑",
                "note": "네이버 쇼핑 최저가 검색", "url": it.get("link", ""), "sample": False,
            })
            n += 1
        note("네이버 쇼핑 API", "ok" if n else "skip", n, kind="api")

    for d in DEAL_SEED:
        out.append({
            "id": mk_id("d", d["query"]), "name": d["name"], "off": d["off"],
            "price": d["price"], "original": d["original"], "store": d["store"],
            "note": d["note"],
            "url": "https://search.shopping.naver.com/search/all?query=" + urllib.parse.quote(d["query"]),
            "sample": not bool(out),
        })
    if not any(not x["sample"] for x in out):
        note("핫딜 큐레이션", "sample", len(out), "API 키 없음 → 예시 가격 유지", kind="deal")
    return out[:10]


# ----------------------------------------------------------------------------
# 6) 오픈소스 · GitHub Trending
# ----------------------------------------------------------------------------
def collect_opensource() -> list[dict]:
    try:
        page = http_get("https://github.com/trending?since=daily").decode("utf-8", "replace")
        blocks = re.findall(r'<article class="Box-row">([\s\S]*?)</article>', page)
        out: list[dict] = []
        for b in blocks[:6]:
            m = re.search(r'<h2[^>]*>[\s\S]*?<a[^>]*href="(/[^"]+)"', b)
            if not m:
                continue
            repo = m.group(1).strip("/").split("?")[0]
            desc_m = re.search(r'<p class="col-9[^"]*">([\s\S]*?)</p>', b)
            star_m = (re.search(r'aria-label="(\d[\d,]*) users starred', b)
                      or re.search(r'stargazers"[\s\S]{0,900}?</svg>\s*([\d,]+)\s*</a>', b))
            stars = int(star_m.group(1).replace(",", "")) if star_m else 0
            out.append({
                "id": mk_id("o", repo), "repo": repo,
                "stars": stars,
                "desc": clean_text(desc_m.group(1))[:200] if desc_m else "",
                "url": "https://github.com/" + repo, "sample": False,
            })
        note("GitHub Trending", "ok" if out else "skip", len(out), kind="opensource")
        return out
    except Exception as exc:  # noqa: BLE001
        note("GitHub Trending", "error", 0, str(exc), kind="opensource")
        return []


# ----------------------------------------------------------------------------
# 7) 앱·게임 순위 (Apple RSS · Steam 공개 API)
# ----------------------------------------------------------------------------
STEAM_NAMES = {730: "Counter-Strike 2", 570: "Dota 2", 578080: "PUBG: BATTLEGROUNDS",
               271590: "GTA V", 1172470: "Apex Legends", 252490: "Rust", 440: "Team Fortress 2",
               1085660: "Destiny 2", 359550: "R6 Siege", 1245620: "ELDEN RING", 1966720: "Lethal Company",
               431960: "Wallpaper Engine", 413150: "Stardew Valley", 1091500: "Cyberpunk 2077",
               292030: "The Witcher 3", 236390: "War Thunder", 553850: "Helldivers 2"}


def collect_apps() -> list[dict]:
    out: list[dict] = []
    try:
        data = json.loads(http_get("https://rss.applemarketingtools.com/api/v2/kr/apps/top-free/10/apps.json", timeout=25))
        for i, app in enumerate(data["feed"]["results"][:8], 1):
            out.append({"id": mk_id("a", app.get("name", str(i))), "platform": "앱스토어",
                        "rank": i, "name": app.get("name", ""),
                        "category": (app.get("genres") or [{}])[0].get("name", "앱") if app.get("genres") else "앱",
                        "publisher": app.get("artistName", ""), "url": app.get("url", ""), "sample": False})
        note("Apple 앱스토어 RSS", "ok" if out else "skip", len(out), kind="apps")
    except Exception as exc:  # noqa: BLE001
        note("Apple 앱스토어 RSS", "error", 0, str(exc), kind="apps")

    try:
        data = json.loads(http_get("https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/", timeout=25))
        ranks = data.get("response", {}).get("ranks", [])[:6]
        s_out = []
        for r in ranks:
            name = STEAM_NAMES.get(r["appid"], f"Steam App {r['appid']}")
            s_out.append({"id": mk_id("g", str(r["appid"])), "platform": "스팀 게임",
                          "rank": int(r["rank"]), "name": name, "category": "게임",
                          "publisher": f"동시접속 {int(r.get('peak_in_game', 0)):,}",
                          "url": f"https://store.steampowered.com/app/{r['appid']}", "sample": False})
        out.extend(s_out)
        note("Steam 최다 플레이", "ok" if s_out else "skip", len(s_out), kind="apps")
    except Exception as exc:  # noqa: BLE001
        note("Steam 최다 플레이", "error", 0, str(exc), kind="apps")
    return out


# ----------------------------------------------------------------------------
# 8) 해커톤 · 공모전 (Devpost 공개 API)
# ----------------------------------------------------------------------------
def collect_hackathons() -> list[dict]:
    try:
        data = json.loads(http_get("https://devpost.com/api/hackathons?status[]=open&order_by=deadline", timeout=25))
        out: list[dict] = []
        for h in data.get("hackathons", [])[:6]:
            deadline = h.get("submission_period_dates", "")
            dday = ""
            m = re.search(r"([A-Z][a-z]{2}) (\d{1,2})", deadline or "")
            if m:
                try:
                    dt = datetime.strptime(f"{m.group(1)} {m.group(2)} {now_kst().year}", "%b %d %Y").replace(tzinfo=KST)
                    if dt < now_kst() - timedelta(days=200):
                        dt = dt.replace(year=dt.year + 1)
                    dday = f"D-{max(0, (dt - now_kst()).days)}"
                except ValueError:
                    dday = ""
            out.append({
                "id": mk_id("h", h.get("title", "")), "name": h.get("title", ""),
                "host": clean_text(h.get("organization_name", "") or "Devpost"),
                "prize": clean_text(h.get("prize_amount", "") or ""),
                "deadline": deadline, "dday": dday or "모집중",
                "url": h.get("url", ""), "sample": False,
            })
        note("Devpost 해커톤", "ok" if out else "skip", len(out), kind="hackathon")
        return out
    except Exception as exc:  # noqa: BLE001
        note("Devpost 해커톤", "error", 0, str(exc), kind="hackathon")
        return []


# ----------------------------------------------------------------------------
# 9) 공공데이터 (나라장터 입찰공고 · 실거래가는 키 필요)
# ----------------------------------------------------------------------------
def collect_build_bids() -> list[dict]:
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not key:
        note("나라장터 입찰공고", "key-missing", 0, "DATA_GO_KR_KEY 미설정", kind="build")
        return []
    try:
        q = urllib.parse.urlencode({
            "serviceKey": key, "pageNo": 1, "numOfRows": 10, "type": "json",
            "inqryDiv": 1, "inqryBgnDt": now_kst().strftime("%Y%m%d") + "0000",
            "inqryEndDt": (now_kst() + timedelta(days=7)).strftime("%Y%m%d") + "2359",
            "bidNtceNm": "건축설계",
        })
        data = json.loads(http_get("https://apis.data.go.kr/1230000/BidPublicInfoService04/getBidPblancListInfoServc?" + q, timeout=25))
        body = data.get("response", {}).get("body", {})
        items = body.get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        out = []
        for i, it in enumerate(items[:8]):
            title = clean_text(it.get("bidNtceNm", ""))
            if not title:
                continue
            out.append({"id": mk_id("p", title), "cat": "build", "source": "나라장터",
                        "title": title, "url": it.get("bidNtceDtlUrl", "https://www.g2b.go.kr"),
                        "time": rel_time(_parse_dt(it.get("bidNtceDt", ""))), "fresh": 0.8,
                        "keywords": ["나라장터", "건축설계"], "sample": False,
                        "meta": {"기관": it.get("ntceInsttNm", ""), "마감": it.get("bidClseDt", "")}})
        note("나라장터 입찰공고", "ok" if out else "skip", len(out), kind="build")
        return out
    except Exception as exc:  # noqa: BLE001
        note("나라장터 입찰공고", "error", 0, str(exc), kind="build")
        return []


# ----------------------------------------------------------------------------
# 특화 5분야 예시 (실데이터가 모자랄 때만 · sample=true 로 명시)
# ----------------------------------------------------------------------------
SPECIAL_SAMPLE = [
    {"cat": "mom", "source": "맘스홀릭", "title": "겨울방학 유아 숲체험 프로그램 어디가 좋아요? 서울 서북권 위주로 아시는 곳",
     "comments": 128, "views": 4210, "keywords": ["겨울방학 숲체험", "유아숲체험", "서울 숲체험"], "rise": 312},
    {"cat": "mom", "source": "레몬테라스", "title": "초1 아이 방과후로 숲놀이 12주 등록했는데 만족도 후기 (사진 많이 넣었어요)",
     "comments": 96, "views": 3180, "keywords": ["숲놀이 후기", "초등 방과후", "겨울방학 숲체험"], "rise": 268},
    {"cat": "mom", "source": "네이버카페", "title": "월드컵공원 숲해설 토요일 10시반반, 이번 주 날씨에 진행될까요?",
     "comments": 41, "views": 1540, "keywords": ["월드컵공원 숲해설", "서울월드컵숲", "주말 숲체험"], "rise": 190},
    {"cat": "estate", "source": "부동산스터디", "title": "전세 심리지수 3주 연속 상승 기사 봤는데, 내년 1월 이사 계획 있으면 지금 움직여야 하나요",
     "comments": 112, "views": 5140, "keywords": ["전세 심리지수", "이사 시즌", "전세 시장"], "rise": 340},
    {"cat": "estate", "source": "부동산스터디", "title": "광진구 강변 테크노마트 근처 10평 사무실, 요즘 실매물 시세 얼마까지 부르나요",
     "comments": 88, "views": 3920, "keywords": ["강변 테크노마트", "소형 사무실", "광진구 사무실"], "rise": 287},
    {"cat": "estate", "source": "호갱노노", "title": "서울 소형 상가 경매 낙찰가율, 11월 들어 확 올랐다는 기사 보셨나요",
     "comments": 57, "views": 2780, "keywords": ["소형 상가 경매", "낙찰가율", "법원경매"], "rise": 205},
    {"cat": "ai", "source": "모두의AI실험실", "title": "클로드 코드로 3시간 만에 만든 부동산 실거래가 대시보드 — 만든 과정 그대로 공유",
     "comments": 143, "views": 6320, "keywords": ["클로드 코드", "바이브코딩", "부동산 대시보드"], "rise": 356},
    {"cat": "ai", "source": "모두의AI실험실", "title": "바이브코딩으로 만든 앱 첫 달 수익 공개 — 광고 12만원, 비용은 0원",
     "comments": 98, "views": 4720, "keywords": ["바이브코딩 수익", "앱 부업", "광고 수익"], "rise": 198},
    {"cat": "ai", "source": "X(트위터)", "title": "X 수익화 프로그램 개편 이후 노출 회복된 계정들, 공통 패턴만 정리해봤습니다",
     "comments": 71, "views": 3410, "keywords": ["X 수익화", "노출 복구", "트위터 알고리즘"], "rise": 241},
    {"cat": "apptech", "source": "뽐뿌", "title": "토스 행운퀴즈 11/21 정답 모음 (오전 9시 기준, 계속 업데이트)",
     "comments": 87, "views": 5880, "keywords": ["토스 행운퀴즈", "앱테크 정답", "오늘의 퀴즈"], "rise": 285},
    {"cat": "apptech", "source": "네이버카페", "title": "쿠팡 파트너스 숏츠로 이번 주 8만원 정산 인증 (주방 수전 편)",
     "comments": 64, "views": 2260, "keywords": ["쿠팡 파트너스 정산", "쇼핑 숏츠", "수전"], "rise": 212},
    {"cat": "apptech", "source": "뽐뿌", "title": "오늘의집 11월 할인 정보 모음 — 냉장고·건조기 실제 체감가 비교",
     "comments": 45, "views": 1980, "keywords": ["오늘의집 할인", "블랙프라이데이", "가전 핫딜"], "rise": 156},
    {"cat": "build", "source": "네이버카페", "title": "나라장터 소규모 건축설계 용역 공고, 11월 3주차 한 번에 정리했습니다",
     "comments": 33, "views": 1120, "keywords": ["나라장터 공고", "건축설계 용역", "입찰 일정"], "rise": 118},
    {"cat": "build", "source": "클리앙", "title": "공동수급 분담이행 실적증명, 지분율 표기에서 자주 틀리는 부분",
     "comments": 28, "views": 940, "keywords": ["분담이행", "실적증명", "지분율"], "rise": 104},
    {"cat": "build", "source": "나라장터", "title": "2027년 공공건축 설계공모 일정 미리 보기 — 상반기 몰리는 달",
     "comments": 22, "views": 780, "keywords": ["설계공모 일정", "공공건축", "2027 공모"], "rise": 97},
]

CAT_LABEL = {"mom": "맘카페·육아", "estate": "부동산·경매", "ai": "AI·부업",
             "apptech": "앱테크·핫딜", "build": "건축·입찰", "comm": "일반커뮤니티",
             "news": "실시간뉴스", "youtube": "유튜브"}


# ----------------------------------------------------------------------------
# 중복 제거 · 스코어링
# ----------------------------------------------------------------------------
def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a[:90], b[:90]).ratio()


def dedupe_items(items: list[dict], key: str = "title", threshold: float = 0.85) -> list[dict]:
    kept: list[dict] = []
    for it in items:
        title = it.get(key, "")
        if not title or any(similar(title, k[key]) >= threshold for k in kept):
            continue
        kept.append(it)
    return kept


def cross_source_counts(items: list[dict], threshold: float = 0.8) -> dict[str, int]:
    """제목이 비슷한 항목을 묶어 출처 종류 수를 셉니다 (교차 출처 지표)."""
    groups: list[dict] = []
    for it in items:
        for g in groups:
            if similar(it["title"], g["title"]) >= threshold:
                g["sources"].add(it.get("source", ""))
                break
        else:
            groups.append({"title": it["title"], "sources": {it.get("source", "")}})
    return {g["title"]: len(g["sources"]) for g in groups}


def score_posts(items: list[dict]) -> None:
    """인기(hot) 0~100 · 급상승(rise) % 추정치."""
    for it in items:
        f = it.get("fresh", 0.5)
        comments = it.get("comments", 0)
        views = it.get("views", 0)
        cross = it.get("cross", 1)
        engagement = min(1.0, (comments / 150.0) * 0.6 + (views / 6000.0) * 0.4)
        base = 0.45 * f + 0.4 * engagement + 0.15 * min(1.0, cross / 3.0)
        it["hot"] = int(round(30 + base * 68))
        it["rise"] = int(round(80 + base * 300))
        it.pop("fresh", None)


def build_ranks(all_posts: list[dict], trends: list[dict]) -> dict:
    """분야별 급상승 키워드 1~7위. Google Trends + 제목 키워드 빈도·최신성."""
    ranks: dict[str, list[dict]] = {}

    trend_rows = []
    for t in trends:
        traffic = t.get("traffic", "")
        num = 0
        m = re.search(r"([\d,]+)", traffic or "")
        if m:
            num = int(m.group(1).replace(",", ""))
        # Google Trends 는 검색량 구간(예: 2,000+)을 줍니다 → 상승 지수로 환산
        r = min(999, 100 + int(num / 20)) if num else 150
        trend_rows.append({"k": t["title"][:24], "r": r, "url": t.get("url", "")})
    ranks["all"] = sorted(trend_rows, key=lambda x: -x["r"])[:7]

    KEYWORD_NOISE = {"GeekNews", "AI·개발", "유튜브", "long", "shorts", "실시간뉴스",
                     "구글뉴스", "나라장터", "건축설계", "종합", "속보"}
    for cat in ["comm", "news", "youtube", "mom", "estate", "ai", "apptech", "build"]:
        counter: dict[str, float] = {}
        for p in all_posts:
            if p.get("cat") != cat:
                continue
            for kw in p.get("keywords", []):
                kw = kw.strip()
                if 1 < len(kw) <= 18 and kw not in KEYWORD_NOISE:
                    counter[kw] = counter.get(kw, 0) + 1 + p.get("hot", 50) / 200.0
        rows = [{"k": k, "r": int(min(400, 90 + v * 55))} for k, v in counter.items()]
        rows.sort(key=lambda x: -x["r"])
        if len(rows) < 7:
            for extra in ranks.get("all", []):
                if len(counter) >= 7:
                    break
                if extra["k"] not in [r["k"] for r in rows]:
                    rows.append(extra)
        if rows:
            ranks[cat] = rows[:7]
    fallback = ranks.get("all") or [{"k": "실시간 트렌드", "r": 120}]
    for cat in CAT_LABEL:
        ranks.setdefault(cat, fallback[:7])
    return ranks


# ----------------------------------------------------------------------------
# 방문 추이 (data/visits.json 이 있으면 실값, 없으면 직전 값 유지 + 샘플)
# ----------------------------------------------------------------------------
def build_visits() -> dict:
    path = ROOT / "data" / "visits.json"
    today = now_kst().date()
    series: list[dict] = []
    source = "sample"
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            series = [r for r in raw.get("days", []) if r.get("d")]
            source = raw.get("source", "manual")
        except Exception:  # noqa: BLE001
            series = []
    by_day = {r["d"]: int(r.get("v", 0)) for r in series if isinstance(r.get("v"), int)}
    demo = {0: 1180, 1: 1340, 2: 1290, 3: 1460, 4: 1520, 5: 1410, 6: 1660}
    days = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        key = d.isoformat()
        val = by_day.get(key, demo[i] if source == "sample" else 0)
        days.append({"d": d.strftime("%m.%d"), "wd": "월화수목금토일"[d.weekday()], "v": val, "iso": key})
    return {"source": source, "days": days}


# ----------------------------------------------------------------------------
# 규칙 기반 브리프 (Gemini 없이도 화면이 완성되게)
# ----------------------------------------------------------------------------
def news_importance(n: dict) -> float:
    """브리프 헤드라인용 중요도: 분야 가중치 + 통신/주요 매체 + 연예·스포츠 감점."""
    section_weight = {"경제·증시": 1.0, "IT·AI": 0.96, "부동산·정책": 0.94, "사회·생활": 0.8}
    score = section_weight.get(n.get("section", ""), 0.6)
    if any(s in n.get("source", "") for s in PREFERRED_SOURCES):
        score += 0.22
    if any(h in n.get("title", "") for h in ENTERTAINMENT_HINTS):
        score -= 0.55
    if len(n.get("title", "")) < 12:
        score -= 0.1
    score += n.get("fresh", 0.5) * 0.18
    return score


def rule_brief(news: list[dict], posts: list[dict], issue_no: int) -> dict:
    """키 없이도 읽히는 브리프. 분야별 상위 기사 + 특화 분야 인기글을 묶습니다."""
    ranked = sorted(news, key=lambda n: -news_importance(n))
    by_section: dict[str, list[dict]] = {}
    for n in ranked:
        by_section.setdefault(n["section"], []).append(n)

    plan = [
        ("econ", "경제·증시", "📈", "경제·증시"),
        ("ai", "IT·AI", "🤖", "IT·AI"),
        ("estate", "부동산·정책", "🏢", "부동산·정책"),
        ("social", "사회·생활", "🧾", "사회·생활"),
    ]
    sections = []
    for key, label, emoji, section in plan:
        items = by_section.get(section, [])[:3]
        if not items:
            continue
        sources = []
        for i in items:
            if i["source"] not in sources:
                sources.append(i["source"])
        lead = items[0]["title"]
        rest = [i["title"] for i in items[1:3]]
        body = f"오늘 {'·'.join(sources[:3])} 등에서 다룬 소식입니다. {lead}"
        if rest:
            body += " 이어서 " + ", ".join(f"'{t[:40]}'" for t in rest) + "도 함께 보도됐습니다."
        points = [f"{i['source']} · {i['title'][:46]}" for i in items]
        sections.append({"key": key, "label": label, "emoji": emoji,
                         "title": lead[:90], "body": body[:420], "points": points})

    # 특화 5분야: 오늘 인기글 1~2건씩
    spec_plan = [("mom", "맘카페·육아", "🌿"), ("estate", "부동산·경매", "🏢"),
                 ("ai", "AI·부업", "🤖"), ("apptech", "앱테크·핫딜", "💰"),
                 ("build", "건축·입찰", "📐")]
    for cat, label, emoji in spec_plan:
        rows = [p for p in posts if p.get("cat") == cat][:2]
        if not rows:
            continue
        if any(x["key"] == cat for x in sections):
            continue
        points = [f"{r['source']} · {r['title'][:46]}" for r in rows]
        sections.append({"key": cat, "label": label, "emoji": emoji,
                         "title": rows[0]["title"][:90],
                         "body": f"{rows[0]['source']}에서 '{rows[0]['title'][:60]}' 글이 반응을 얻고 있습니다." +
                                 (f" {rows[1]['source']}에서도 비슷한 흐름의 글이 올라왔습니다." if len(rows) > 1 else ""),
                         "points": points})

    if not sections:
        sections = [{"key": "comm", "label": "커뮤니티", "emoji": "💬",
                     "title": "오늘 수집된 인기글", "body": "수집 결과가 적은 날입니다.",
                     "points": [p["title"][:50] for p in posts[:3]]}]

    heads = [x["title"] for x in sections[:3]]
    lead = "오늘은 " + ", ".join(f"'{h[:34]}'" for h in heads[:2]) + " 등이 눈에 띕니다. "
    if len(heads) > 2:
        lead += f"이 밖에 {sections[2]['label']} 쪽에서 '{heads[2][:34]}' 흐름이 이어졌습니다. "
    lead += f"수집된 {len(news) + len(posts)}건 가운데 분야별로 {len(sections)}개 이슈를 골랐습니다."

    return {
        "no": f"No.{issue_no:02d}",
        "date": now_kst().strftime("%Y-%m-%d"),
        "label": now_kst().strftime("%m.%d"),
        "title": " · ".join(h[:34] for h in heads[:3]) or "오늘의 트렌드 리포트",
        "lead": lead[:600],
        "metrics": {"deep": len(sections), "analysis": max(1, len(news) // 8),
                    "cross": sum(1 for p in posts if p.get("cross", 1) > 1)},
        "sections": sections[:6],
        "engine": "rule-based",
        "past": [],
    }


def attach_history(payload: dict) -> None:
    """오늘 브리프를 data/history/YYYY-MM-DD.json 으로 남기고, 최근 5회를 지난 호로 붙입니다."""
    hist_dir = ROOT / "data" / "history"
    hist_dir.mkdir(parents=True, exist_ok=True)
    today = now_kst().strftime("%Y-%m-%d")
    snap = {"date": today, "issue": payload.get("issue"), "generated_at": payload.get("generated_at"),
            "brief": payload.get("brief"), "stats": payload.get("stats"),
            "ranks": (payload.get("ranks") or {}).get("all")}
    (hist_dir / f"{today}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

    past = []
    files = sorted(hist_dir.glob("????-??-??.json"), reverse=True)
    for f in files[:6]:
        if f.stem == today:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            b = d.get("brief") or {}
            if b.get("title"):
                past.append({"no": b.get("no", d.get("date", "")), "date": b.get("date", f.stem),
                             "title": b.get("title", ""), "lead": b.get("lead", ""),
                             "sections": b.get("sections", [])})
        except Exception:  # noqa: BLE001
            continue
    payload.setdefault("brief", {})["past"] = past[:5]


# ----------------------------------------------------------------------------
# 메인
# ----------------------------------------------------------------------------
def issue_number() -> int:
    state = ROOT / "data" / "issue.json"
    try:
        n = int(json.loads(state.read_text(encoding="utf-8")).get("no", 0)) + 1
    except Exception:  # noqa: BLE001
        n = 1
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"no": n, "at": now_kst().isoformat()}, ensure_ascii=False), encoding="utf-8")
    return n


def collect_trends() -> list[dict]:
    items = collect_feed("Google Trends KR", "https://trends.google.co.kr/trending/rss?geo=KR",
                         kind="trend", limit=10)
    return items


def build_payload() -> dict:
    started = time.time()
    log("수집 시작 · 노리짱 트래픽센트 v2")
    issue_no = issue_number()

    # --- 커뮤니티
    comm_posts: list[dict] = []
    for name, url, key in COMMUNITY_SCRAPE:
        rows = scrape_community(name, url, key)
        for i, r in enumerate(rows):
            comm_posts.append({
                "id": mk_id("c", r["title"]),
                "cat": "comm", "source": name, "source_key": key,
                "title": r["title"], "url": r["url"],
                "published": "", "time": "최근", "rise": 120, "hot": 60,
                "comments": 0, "views": 0,
                "keywords": [name], "sample": False,
                "thumb": thumb_for("comm", name, r["title"]),
            })
    # 실수집 0건인 소스는 예시 카드로 채워 '커뮤니티 9곳'이 화면에서 빠지지 않게
    got_keys = {p["source_key"] for p in comm_posts}
    for key, rows in COMMUNITY_SAMPLE.items():
        if key in got_keys:
            continue
        for name, title in rows:
            comm_posts.append({
                "id": mk_id("c", name + title), "cat": "comm", "source": name, "source_key": key,
                "title": title, "url": "", "published": "", "time": "예시",
                "rise": 130, "hot": 55, "comments": 0, "views": 0,
                "keywords": [name], "sample": True, "thumb": thumb_for("comm", name, title),
            })
    # 소스별 3건씩 균형 있게 (한 커뮤니티가 화면을 독차지하지 않도록)
    by_src: dict[str, list[dict]] = {}
    for post in comm_posts:
        by_src.setdefault(post["source_key"], []).append(post)
    balanced: list[dict] = []
    for _, _, key in COMMUNITY_SCRAPE:
        balanced.extend(by_src.get(key, [])[:3])
    comm_posts = dedupe_items(balanced)[:20]
    for p in comm_posts:
        p["fresh"] = 0.55 + (0.1 if p["source_key"] in ("dcbest", "natepann") else 0)

    # --- 뉴스 · 유튜브 · 블로그 · 핫딜 · 오픈소스 · 앱 · 해커톤
    news = collect_news()
    videos = collect_youtube()
    blogs = collect_blogs()
    deals = collect_deals()
    opensource = collect_opensource()
    apps = collect_apps()
    hackathons = collect_hackathons()
    build_posts = collect_build_bids()
    trends = collect_trends()

    # --- 특화 5분야 (실데이터 + 예시 보충)
    special: list[dict] = []
    for s in SPECIAL_SAMPLE:
        post = {
            "id": mk_id("s", s["title"]), "cat": s["cat"], "source": s["source"],
            "title": s["title"], "url": "", "published": "",
            "time": "예시", "rise": s["rise"], "hot": 70,
            "comments": s["comments"], "views": s["views"],
            "keywords": s["keywords"], "sample": True,
            "thumb": thumb_for(s["cat"], s["source"], s["title"]),
        }
        special.append(post)
    special.extend(build_posts)

    # GeekNews(개발/스타트업)를 AI·부업 인기글로 활용
    for i, b in enumerate(blogs[:4]):
        if b["source"] == "GeekNews":
            special.append({
                "id": mk_id("s", b["title"]), "cat": "ai", "source": "GeekNews",
                "title": b["title"], "url": b["url"], "published": "",
                "time": b["time"], "rise": 150 - i * 8, "hot": 72 - i * 3,
                "comments": 0, "views": 0, "keywords": ["GeekNews", "AI·개발"],
                "sample": False, "thumb": thumb_for("ai", "GeekNews", b["title"]),
            })

    all_posts = comm_posts + special
    cross = cross_source_counts(news + all_posts)
    for p in all_posts:
        p["cross"] = max(1, cross.get(p["title"], 1))
        p.setdefault("fresh", 0.5)
    score_posts(all_posts)

    # --- 뉴스 카드에도 인기 지표 부여 (통합 피드에서 같은 카드로 보이도록)
    for i, n in enumerate(news):
        n["cat"] = "news"
        n["hot"] = max(40, 85 - i)
        n["rise"] = max(90, 260 - i * 6)
        n["comments"] = 0
        n["views"] = 0
        n["thumb"] = thumb_for("news", n["source"], n["title"])
        n["sample"] = False

    for v in videos:
        v["cat"] = "youtube"
        v["source"] = v.get("channel", "YouTube")
        v["hot"] = max(42, 76 - int(v.get("rank", 50)))
        v["rise"] = max(95, 250 - int(v.get("rank", 50)) * 5)
        v["comments"] = 0
        v["time"] = v.get("time") or "최근"
        v["keywords"] = ["유튜브", v.get("kind", "long")]

    all_posts.sort(key=lambda x: -x["hot"])
    visited_sources = ({p["source"] for p in comm_posts} | {n["source"] for n in news}
                       | {v.get("channel", "YouTube") for v in videos} | {b["source"] for b in blogs})
    stats = {
        "sources": len(visited_sources),
        "collected": len(all_posts) + len(news) + len(videos) + len(blogs) + len(deals),
        "cross_sources": sum(1 for p in all_posts if p.get("cross", 1) > 1),
        "live_sources": sum(1 for r in COLLECT_LOG if r["status"] == "ok"),
        "skipped_sources": sum(1 for r in COLLECT_LOG if r["status"] in ("skip", "error", "key-missing")),
        "elapsed_sec": round(time.time() - started, 1),
    }

    payload = {
        "schema": "nori-traffic-scent/2",
        "generated_at": now_kst().isoformat(timespec="seconds"),
        "issue": {"no": issue_no, "label": f"No.{issue_no:02d} ({now_kst():%m.%d})",
                  "date": now_kst().strftime("%Y-%m-%d")},
        "stats": stats,
        "sources": sorted(visited_sources),
        "youtube_mode": "api" if os.environ.get("YOUTUBE_API_KEY", "").strip() else "channel-rss",
        "site": {
            "repo": os.environ.get("GITHUB_REPOSITORY", "").strip(),
            "pages_url": ("https://" + os.environ.get("GITHUB_REPOSITORY", "").split("/")[0].lower()
                          + ".github.io/" + os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1]
                          + "/") if os.environ.get("GITHUB_REPOSITORY", "").strip() else "",
        },
        "posts": all_posts,
        "news": news,
        "videos": videos,
        "blogs": blogs,
        "deals": deals,
        "opensource": opensource,
        "apps": apps,
        "hackathons": hackathons,
        "benchmarks": BENCHMARKS,
        "indie": INDIE,
        "ranks": build_ranks(all_posts + news, trends),
        "brief": rule_brief(news, all_posts, issue_no),
        "visits": build_visits(),
        "collect_log": COLLECT_LOG,
        "notes": [
            "posts 중 sample=true 는 실수집이 아닌 예시 데이터입니다(화면에는 ‘예시’ 표시).",
            "rise 값은 최신성·댓글·조회·교차 출처를 합산한 추정치입니다.",
            "뉴스·유튜브·오픈소스·앱·해커톤은 공개 RSS/API 실데이터입니다.",
        ],
    }
    attach_history(payload)
    return payload


# --- 수동 큐레이션 (sources.yaml benchmarks 와 같은 내용 · 키 없이도 화면 유지)
BENCHMARKS = {
    "metric": "지능",
    "rows": [
        {"rank": 1, "model": "Gemini 2.5 Flash", "vendor": "Google", "score": 74, "note": "무료 티어 · 요약/속도 균형"},
        {"rank": 2, "model": "Claude Sonnet 4.5", "vendor": "Anthropic", "score": 73, "note": "문장 품질"},
        {"rank": 3, "model": "GPT-5", "vendor": "OpenAI", "score": 71, "note": "범용"},
        {"rank": 4, "model": "Qwen3 32B", "vendor": "Alibaba", "score": 64, "note": "오픈웨이트"},
        {"rank": 5, "model": "Llama 4 70B", "vendor": "Meta", "score": 61, "note": "로컬 실행 가능"},
    ],
    "source": "수동 큐레이션(월 1회 갱신) · 벤치마크 점수는 참고용",
}

INDIE = [
    {"id": "i1", "tab": "meta", "cat": "메타버스 · 종교", "emoji": "🏯", "name": "산사 · 온라인 절",
     "desc": "청연당에서 함께 절하고 합장하며 염주를 굴려요. 연등 산책길과 연꽃 연못, 달빛 마당도 둘러볼 수 있어요.",
     "likes": 0, "maker": "인디 사례", "url": "",
     "detail": {"문제": "오프라인 절 체험을 온라인에서 가볍게 경험하고 싶다는 수요.", "기능": "가상 공간 산책 · 절하기 인터랙션 · 연등/연못 배경.", "스택": "웹 3D · 정적 호스팅", "시간": "사례"}},
    {"id": "i2", "tab": "meta", "cat": "메타버스 · 놀이", "emoji": "❄️", "name": "눈 오는 마을 · 크리스마스 마켓",
     "desc": "눈 내리는 마을을 함께 걷고 선물 상자를 찾거나 썰매를 타요. 마켓에서 부스를 구경하고 도장도 모을 수 있어요.",
     "likes": 0, "maker": "인디 사례", "url": "",
     "detail": {"문제": "겨울 시즌 이벤트를 웹에서 가볍게 열고 싶은 소규모 팀.", "기능": "마을 산책 · 선물 찾기 · 도장 모으기.", "스택": "웹 3D", "시간": "사례"}},
    {"id": "i3", "tab": "game", "cat": "웹 게임 · 퍼즐", "emoji": "🎸", "name": "KÖTTBULLAR METAL",
     "desc": "이케아 제품 이름으로 만든 데스메탈 가사. 15분 모시핏을 버틸 수 있나요?",
     "likes": 0, "maker": "인디 사례", "url": "",
     "detail": {"문제": "짧은 시간에 웃음 터지는 미니게임.", "기능": "리듬·서바이벌 게임 루프.", "스택": "웹 게임", "시간": "사례"}},
    {"id": "i4", "tab": "game", "cat": "웹 게임 · 시뮬", "emoji": "🍔", "name": "BUNGR INC.",
     "desc": "버거를 만들어 자유를 얻는 경영 시뮬레이션.",
     "likes": 0, "maker": "인디 사례", "url": "",
     "detail": {"문제": "탭 몇 번으로 즐기는 경영 게임.", "기능": "재료 조합 · 판매 · 성장.", "스택": "웹 게임", "시간": "사례"}},
    {"id": "i5", "tab": "life", "cat": "생활 · 앱테크", "emoji": "🌿", "name": "숲놀이 사진 자동 정리함",
     "desc": "현장 사진을 날짜·프로그램별로 폴더 정리하고 아이 얼굴 영역을 자동으로 흐리게 만드는 1인용 웹툴.",
     "likes": 128, "maker": "노리짱 · 클로드 코드", "url": "",
     "detail": {"문제": "사진 수백 장 분류·얼굴 가리기에 매번 2시간 이상.", "기능": "자동 폴더 분류 · 얼굴 블러 · 썸네일 생성.", "스택": "HTML + JS + 얼굴 감지", "시간": "3시간 20분"}},
    {"id": "i6", "tab": "util", "cat": "웹 유틸", "emoji": "🔗", "name": "쿠팡 링크 + 고지문 생성기",
     "desc": "상품 링크를 넣으면 추적 링크와 공정위 고지 문구 3종을 한 번에 만들어 주는 유틸.",
     "likes": 143, "maker": "노리짱 · 클로드 코드", "url": "",
     "detail": {"문제": "고지 문구를 세 번 따로 붙여넣다 빠뜨림.", "기능": "링크 정규화 · 고지문 3종 복사 · 체크리스트.", "스택": "단일 HTML + JS", "시간": "1시간 30분"}},
]


def main() -> int:
    ap = argparse.ArgumentParser(description="노리짱 트래픽센트 v2 수집기")
    ap.add_argument("--out", default=str(ROOT / "data.json"))
    args = ap.parse_args()

    payload = build_payload()
    MIN_ITEMS = 25
    total = len(payload["posts"]) + len(payload["news"]) + len(payload["videos"])
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if total < MIN_ITEMS and out_path.exists():
        log(f"수집 항목 {total}건 < 기준 {MIN_ITEMS}건 → 기존 data.json 유지 (덮어쓰지 않음)")
        return 2

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"data.json 저장 · {out_path} ({out_path.stat().st_size:,} bytes)")
    log(f"항목 수: 커뮤니티 {len(payload['posts'])} · 뉴스 {len(payload['news'])} · "
        f"유튜브 {len(payload['videos'])} · 블로그 {len(payload['blogs'])} · 핫딜 {len(payload['deals'])}")
    ok = sum(1 for r in payload["collect_log"] if r["status"] == "ok")
    skip = sum(1 for r in payload["collect_log"] if r["status"] in ("skip", "error"))
    keyless = sum(1 for r in payload["collect_log"] if r["status"] == "key-missing")
    log(f"소스 상태: 성공 {ok} · 건너뜀/실패 {skip} · 키 미설정 {keyless}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
