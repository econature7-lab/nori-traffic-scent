#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
트렌드픽(TrendPick) v3 · collector.py
=====================================
공개 RSS / 공개 HTML / 선택적 API 키를 읽어 data.json 하나로 정리합니다.
(표준 라이브러리만으로 동작 · pip install 없이 실행 가능)

수집 영역
  1) 커뮤니티 인기글 : 네이트판 · 더쿠 · 보배드림 · 82cook (공개 목록 1회 요청)
  2) 실시간 뉴스     : 매일경제 · 연합뉴스(경제·산업·정치·사회) · 전자신문 · AI타임스 · 조선일보
  3) 유튜브          : (키 있으면) Data API 인기 급상승, 없으면 채널 공개 RSS
  4) 블로그 글감     : GeekNews · 슬로우뉴스 · 바이라인네트워크 (+ 네이버 블로그 API)
  5) 핫딜            : (키 있으면) 네이버 쇼핑 최저가 — 없으면 화면은 실수집 '특가·할인' 소식으로 대체
  6) 오픈소스        : GitHub Trending + 저장소 오픈그래프 이미지
  7) 앱·게임 순위    : Apple 앱스토어 RSS(실패 시 iTunes JSON) + Steam 최다 플레이
  8) 해커톤·공모전   : Devpost 공개 API
  9) 급상승 키워드   : Google Trends KR + 수집 제목 키워드 (TOP 10)
 10) 주제 분류       : 수집 결과를 맘카페·육아 / 부동산·경매 / AI·부업 / 앱테크·핫딜 / 건축·입찰 로 태깅

v3 썸네일 원칙 (실제 이미지 우선)
  - RSS media:group > media:thumbnail / media:content / enclosure / 본문 <img> 를 먼저 읽습니다.
  - 유튜브는 URL 에서 video_id 를 뽑아 https://i.ytimg.com/vi/{id}/hqdefault.jpg 를 100% 보장합니다.
  - 이미지가 없는 기사는 og:image / twitter:image 를 짧은 타임아웃(6초)·동시성 8로 추출하며,
    연속 실패한 호스트는 이번 실행에서 건너뜁니다.
  - 이미지가 끝내 없으면 화면이 카테고리별 SVG 일러스트로 대체합니다(깨진 이미지 없음).

원칙
  - 외부 사이트에는 1회 요청, UA 표기, 타임아웃, 실패는 예외 없이 skip 로그.
  - 수집 실패·키 미설정은 data.json 의 collect_log 에 남기고 나머지는 계속 진행.
  - 실데이터가 아닌 항목은 만들지 않습니다(‘예시’ 카드 없음).

사용법
  python collector.py                 # work/nori-traffic-scent/data.json 생성
  python collector.py --out custom.json
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree as ET

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent
SCHEMA = "trendpick/3"

# 실제 브라우저 UA. (봇 표기를 붙이면 한국경제·개드립 등에서 403 이 나므로 표준 UA 사용)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
TIMEOUT = 15
OG_TIMEOUT = 6
MAX_PER_FEED = 12

COLLECT_LOG: list[dict] = []

MRSS = "http://search.yahoo.com/mrss/"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ht": "https://trends.google.com/trending/rss",
    "media": MRSS,
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


# ----------------------------------------------------------------------------
# 로그 · 유틸
# ----------------------------------------------------------------------------
def now_kst() -> datetime:
    return datetime.now(KST)


def log(msg: str) -> None:
    print(f"[{now_kst():%H:%M:%S}] {msg}", flush=True)


def note(source: str, status: str, count: int = 0, error: str = "", kind: str = "") -> None:
    """수집 결과를 남깁니다. status: ok | skip | key-missing | error | replaced"""
    COLLECT_LOG.append({
        "source": source, "kind": kind, "status": status,
        "count": int(count), "error": str(error)[:180],
    })
    mark = {"ok": "OK  ", "skip": "SKIP", "key-missing": "KEY ", "error": "ERR ",
            "replaced": "SWAP"}.get(status, "----")
    line = f"  {mark} {source:<22} {count:>3}건"
    if error:
        line += f"  ({str(error)[:90]})"
    print(line, flush=True)


def http_get(url: str, timeout: int = TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": ("application/rss+xml, application/atom+xml, application/xml, application/json, "
                   "text/html;q=0.8, */*;q=0.5"),
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
    """'제목 - 매체명' 형태의 RSS 접미사 제거 (구글뉴스·일부 피드)."""
    return re.sub(r"\s+-\s+[^-]{2,22}$", "", title).strip()


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


# ----------------------------------------------------------------------------
# 이미지 유틸
# ----------------------------------------------------------------------------
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp")
IMG_BAD_BITS = ("1x1", "pixel.gif", "blank.gif", "spacer.gif", "transparent.gif",
                "logo_default", "no_image", "noimage", "default_thumb",
                "og-talk.png", "og_default", "default_og", "og_image.png")
# og:image 로는 쓰이지만 실제 이미지가 아닌(링크 미리보기) 호스트
NON_IMAGE_HOSTS = {"social.news.hada.io"}


def _norm_img(url: str, base: str = "") -> str:
    if not url:
        return ""
    u = html_mod.unescape(url.strip())
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("/") and base:
        u = urllib.parse.urljoin(base, u)
    elif base and not u.startswith("http"):
        u = urllib.parse.urljoin(base, u)
    if not u.startswith("http"):
        return ""
    low = u.lower()
    if urllib.parse.urlparse(low).netloc in NON_IMAGE_HOSTS:
        return ""
    if any(b in low for b in IMG_BAD_BITS):
        return ""
    if low.startswith("data:"):
        return ""
    return u


def _first_img_in_html(fragment: str, base: str = "") -> str:
    if not fragment:
        return ""
    for m in re.finditer(r"<img[^>]+(?:src|data-src)=[\"']([^\"']+)[\"']", fragment, re.I):
        u = _norm_img(m.group(1), base)
        if u:
            return u
    return ""


def pick_feed_image(item_el, entry_url: str = "") -> str:
    """RSS/Atom item 에서 대표 이미지 URL 을 고릅니다 (media > enclosure > 본문 img 순)."""
    # 1) media:group / media:thumbnail / media:content(medium=image)
    for tag in ("thumbnail", "content"):
        for node in item_el.iter("{%s}%s" % (MRSS, tag)):
            medium = (node.get("medium") or "").lower()
            mtype = (node.get("type") or "").lower()
            if tag == "content" and not (medium == "image" or mtype.startswith("image")):
                continue
            u = _norm_img(node.get("url") or "", entry_url)
            if u:
                return u
    # 2) <enclosure type="image/jpeg" url="...">
    for node in item_el.iter("enclosure"):
        if (node.get("type") or "").lower().startswith("image"):
            u = _norm_img(node.get("url") or "", entry_url)
            if u:
                return u
    for node in item_el.findall("atom:link", NS):
        if (node.get("rel") or "") == "enclosure" and (node.get("type") or "").startswith("image"):
            u = _norm_img(node.get("href") or "", entry_url)
            if u:
                return u
    # 3) 본문 안의 <img> (description / content / summary)
    for path in ("description", "atom:content", "atom:summary", "content"):
        node = item_el.find(path, NS)
        if node is None:
            continue
        raw = node.text or ""
        if not raw:
            raw = ET.tostring(node, encoding="unicode")
        u = _first_img_in_html(raw, entry_url)
        if u:
            return u
    return ""


def yt_video_id(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""


def yt_thumb(video_id: str) -> str:
    """유튜브 썸네일은 hqdefault 가 사실상 항상 존재합니다(100% 보장용)."""
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else ""


# ----------------------------------------------------------------------------
# RSS / Atom 파서
# ----------------------------------------------------------------------------
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
    """RSS 2.0 / Atom 1.0 을 공통 dict 리스트로 변환 (대표 이미지 포함)."""
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"XML 파싱 실패: {exc}") from exc

    if root.tag.endswith("rss") or root.find("channel", NS) is not None:
        for it in root.iter("item"):
            title = clean_text(_find_text(it, "title"))
            link = html_mod.unescape(_find_text(it, "link") or _find_text(it, "guid"))
            desc = clean_text(_find_text(it, "description"))
            pub = _parse_dt(_find_text(it, "pubDate", "dc:date"))
            traffic = _find_text(it, "ht:approx_traffic")
            keywords = [clean_text(k.text or "") for k in it.findall("category")]
            if not title:
                continue
            items.append({
                "title": strip_source_suffix(title), "url": link, "desc": desc,
                "published": pub, "traffic": traffic,
                "tags": [k for k in keywords if k],
                "img": pick_feed_image(it, link),
                "picture": _norm_img(_find_text(it, "ht:picture"), link),
                "news_url": html_mod.unescape(_find_text(it, "ht:news_item_url")),
                "news_source": clean_text(_find_text(it, "ht:news_item_source")),
            })
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
            vid = _find_text(it, "yt:videoId")
            items.append({
                "title": title, "url": link, "desc": desc,
                "published": pub, "traffic": "", "tags": [],
                "img": pick_feed_image(it, link),
                "video_id": vid or yt_video_id(link),
                "picture": "", "news_url": "", "news_source": "",
            })
    return items


def collect_feed(name: str, url: str, kind: str = "news", limit: int = MAX_PER_FEED,
                 fallbacks: tuple[str, ...] = ()) -> list[dict]:
    for candidate in (url,) + tuple(fallbacks):
        try:
            data = http_get(candidate)
            items = parse_feed(data)[:limit]
            if not items:
                raise ValueError("항목 0건")
            note(name, "ok", len(items), kind=kind)
            for it in items:
                it["source_name"] = name
            return items
        except Exception as exc:  # noqa: BLE001 - 어떤 실패도 수집 중단 사유가 되지 않게
            last = exc
    note(name, "error", 0, str(last), kind=kind)
    return []


# ----------------------------------------------------------------------------
# og:image 보강 (이미지 없는 기사만 · 짧은 타임아웃 · 동시성 제한)
# ----------------------------------------------------------------------------
_HOST_FAIL: dict[str, int] = {}
OG_SKIP_HOSTS = {
    "news.google.com", "www.google.com", "google.com", "localhost",
    "www.dcinside.com", "gall.dcinside.com", "m.dcinside.com",
    "www.fmkorea.com", "www.dogdrip.net", "www.instiz.net",
    "bbs.ruliweb.com", "www.ppomppu.co.kr", "www.todayhumor.co.kr",
}
_HOST_LAST = {"t": 0.0}


def og_image(page_url: str) -> str:
    """기사 페이지의 og:image / twitter:image / link[rel=image_src] 를 읽습니다."""
    parsed = urllib.parse.urlparse(page_url)
    host = parsed.netloc.lower()
    if not host or host in OG_SKIP_HOSTS:
        return ""
    if _HOST_FAIL.get(host, 0) >= 2:
        return ""
    try:
        raw = http_get(page_url, timeout=OG_TIMEOUT)
    except Exception:  # noqa: BLE001
        _HOST_FAIL[host] = _HOST_FAIL.get(host, 0) + 1
        return ""
    head = raw[:400000].decode("utf-8", "replace")
    patterns = (
        r'<meta[^>]+(?:property|name)=["\']og:image(?::url)?["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']og:image(?::url)?["\']',
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]*content=["\']([^"\']+)["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]*href=["\']([^"\']+)["\']',
    )
    for pat in patterns:
        m = re.search(pat, head, re.I)
        if not m:
            continue
        u = _norm_img(m.group(1), page_url)
        if not u:
            continue
        # og:image 가 기사 URL 자체나 페이지 링크를 가리키는 경우는 제외
        if u.rstrip("/") == page_url.rstrip("/"):
            continue
        return u
    return ""


def enrich_images(items: list[dict], budget_sec: float = 45.0, workers: int = 8,
                  limit: int = 60) -> int:
    """이미지 없는 항목에 og:image 를 채웁니다. 반환값은 새로 채운 개수."""
    seen: set[str] = set()
    targets: list[dict] = []
    for it in items:
        if it.get("img"):
            continue
        u = (it.get("url") or "").strip()
        if not u.startswith("http") or u in seen:
            continue
        seen.add(u)
        targets.append(it)
    targets = targets[:limit]
    if not targets:
        return 0
    filled = 0
    started = time.time()
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = {pool.submit(og_image, it["url"]): it for it in targets}
        try:
            for fut in as_completed(futures, timeout=budget_sec):
                it = futures[fut]
                try:
                    img = fut.result()
                except Exception:  # noqa: BLE001
                    img = ""
                if img and not it.get("img"):
                    it["img"] = img
                    filled += 1
        except Exception:  # noqa: BLE001 - 예산 초과분은 버립니다
            pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    log(f"  og:image 보강 {filled}/{len(targets)}건 · {time.time() - started:.1f}s")
    return filled


# ----------------------------------------------------------------------------
# 1) 커뮤니티 인기글 (공개 목록 1회 요청)
# ----------------------------------------------------------------------------
# (이름, URL, 키, 게시글 URL 패턴)
# 개드립(403) · 에펨코리아(430) · 루리웹(타임아웃) · 클리앙/인스티즈(JS 렌더링) · 뽐뿌(403)는
# 제목이 HTML 에 없어 v3 에서 제외하고, 실제로 수집되는 목록으로 교체했습니다.
COMMUNITY_SCRAPE = [
    ("네이트판", "https://pann.nate.com/talk/ranking", "natepann", r"/talk/\d+"),
    ("더쿠", "https://theqoo.net/hot", "theqoo", r"/hot/\d+"),
    ("보배드림", "https://www.bobaedream.co.kr/list?code=best", "bobaedream", r"view\?[^\"']*No=\d+"),
    ("82cook", "https://www.82cook.com/entiz/enti.php?bn=15", "82cook", r"num=\d+"),
]

NAV_NOISE = {
    "주요메뉴로 바로가기", "오늘의 자동차 바로가기", "하단정보로 바로가기", "시승기·배틀·목격담",
    "토픽필터", "아이디 · 비밀번호 찾기", "제보 및 기타 제안", "내가 본 글 기능 안내",
    "책임의 한계와 법적고지", "실시간 베스트 갤러리", "톡커들의 선택 명예의 전당",
    "클리앙 공식 앱 출시 안내 -1.1.9 업데이트", "모두의공원 게시판 이용규칙",
    "회원가입", "로그인", "검색", "이용규칙", "개인정보처리방침", "광고/제휴", "이용 문의",
}
NOISE_BITS = ("바로가기", "이용규칙", "업데이트 안내", "개인정보", "명예의 전당", "즐겨찾기",
              "비밀번호", "회원가입", "로그인", "앱 설치", "앱 버전", "저작권", "고객센터")


def scrape_community(name: str, url: str, key: str, pattern: str) -> list[dict]:
    try:
        page = http_get(url).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        note(name, "skip", 0, f"차단/접속 실패: {exc}")
        return []

    out: list[dict] = []
    seen: set[str] = set()
    rx = re.compile(r'<a\b[^>]*href="([^"]*' + pattern + r'[^"]*)"[^>]*>([^<>]{6,140})</a>', re.I)
    for href, raw in rx.findall(page):
        title = clean_text(raw)
        href = html_mod.unescape(href)
        if not title or len(title) < 8 or not re.search(r"[가-힣]", title):
            continue
        if title in NAV_NOISE or any(b in title for b in NOISE_BITS):
            continue
        if is_sensitive(title):
            continue  # 선정적·자극적 제목은 커뮤니티 수집에서 제외
        if title in seen:
            continue
        seen.add(title)
        link = href if href.startswith("http") else urllib.parse.urljoin(url, href)
        out.append({
            "title": title, "url": link, "desc": "", "published": None,
            "traffic": "", "tags": [], "img": "", "source_name": name, "source_key": key,
        })
        if len(out) >= 6:
            break

    note(name, "ok" if out else "skip", len(out), "" if out else "제목 패턴 미검출", kind="community")
    return out


# ----------------------------------------------------------------------------
# 2) 실시간 뉴스
# ----------------------------------------------------------------------------
# (분야, 매체, URL, 종합 피드 여부)
# 한국경제 RSS 는 데이터센터 IP·반복 요청에서 403 이 반복되어,
# 실제로 수집되는 매일경제 + 연합뉴스 경제 피드로 대체했습니다(둘 다 대표 이미지 포함).
# (피드 분야, 매체, URL, 키워드 미검출 시 기본 분야)
# 피드 분야는 '어디서 왔는지'이고, 화면 분야는 제목 키워드로 다시 정합니다.
# 예전에는 연합뉴스 산업·정치 피드를 통째로 부동산·정책으로 두어
# 농수산·사회 기사가 부동산으로 분류됐습니다 → 기본값을 일반 분야로 내렸습니다.
NEWS_FEEDS = [
    ("경제·증시", "매일경제", "https://www.mk.co.kr/rss/30000001/", "사회·생활"),
    ("경제·증시", "연합뉴스 경제", "https://www.yna.co.kr/rss/economy.xml", "경제·증시"),
    ("IT·AI", "전자신문", "https://rss.etnews.com/Section901.xml", "사회·생활"),
    ("IT·AI", "AI타임스", "https://www.aitimes.com/rss/allArticle.xml", "IT·AI"),
    ("부동산·정책", "매일경제 부동산", "https://www.mk.co.kr/rss/50300009/", "부동산·정책"),
    ("부동산·정책", "연합뉴스 산업", "https://www.yna.co.kr/rss/industry.xml", "사회·생활"),
    ("부동산·정책", "연합뉴스 정치", "https://www.yna.co.kr/rss/politics.xml", "사회·생활"),
    ("사회·생활", "연합뉴스 사회", "https://www.yna.co.kr/rss/society.xml", "사회·생활"),
    ("사회·생활", "조선일보", "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml", "사회·생활"),
]
NEWS_SECTION_ORDER = ["경제·증시", "IT·AI", "부동산·정책", "사회·생활"]

ENTERTAINMENT_HINTS = ("열애", "결혼", "컴백", "불화", "아이돌", "드라마", "예능", "배우", "가수",
                       "앨범", "콘서트", "시구", "승리", "패배", "농구", "야구", "축구", "배구",
                       "골프", "올림픽", "MAMA", "그래미", "팬미팅")
PREFERRED_SOURCES = ("연합뉴스", "매일경제", "전자신문", "AI타임스", "조선일보")


def kw_hit(text_low: str, word: str) -> bool:
    """짧은 영문 키워드(AI·IT·GPU·LH)는 단어 경계로, 한글은 부분 일치로 찾습니다.

    경계를 안 쓰면 'AI'가 'mail·air' 같은 문자열 안에서도 걸려 오분류됩니다.
    """
    w = word.lower().strip()
    if w and re.fullmatch(r"[a-z0-9 .:_-]+", w) and len(w) <= 8:
        return re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", text_low) is not None
    return w in text_low


# 사고·재난 기사는 '주택·아파트'라는 단어만으로 부동산 뉴스가 되지 않게 합니다.
ACCIDENT_HINTS = ("화재", "불이 났", "대피", "숨져", "숨진", "사망자", "부상자", "흡입", "붕괴",
                  "매몰", "실종", "화상")
ESTATE_MARKET_HINTS = ("집값", "전셋값", "매매가", "분양", "청약", "경매", "공매", "낙찰", "재건축",
                       "재개발", "입주", "미분양", "공시가격", "아파트값", "부동산 시장", "매매")


def is_accident(text: str) -> bool:
    return any(h in (text or "") for h in ACCIDENT_HINTS)


def section_rules(title: str, default: str) -> str:
    """기사 제목 키워드로 화면 분야를 정합니다(피드 분야는 참고만).

    '정부·국회·대통령·정책·세제·금리' 같은 넓은 단어는 부동산·정책에서 뺐습니다.
    그 단어들이 일반 정치·경제 기사를 부동산으로 끌어와 탭이 오염됐습니다.
    """
    low = title.lower()
    if is_accident(title) and not any(kw_hit(low, w) for w in ESTATE_MARKET_HINTS):
        return "사회·생활"
    rules = [
        ("IT·AI", ("AI", "인공지능", "반도체", "스마트폰", "클라우드", "로봇", "플랫폼",
                   "게임", "통신", "데이터센터", "소프트웨어", "삼성전자", "LG전자", "네이버", "카카오",
                   "구글", "애플", "배터리", "디스플레이", "메타버스", "5G", "챗봇", "자율주행",
                   "디지털자산", "가상자산", "스테이블코인", "블록체인", "코인 발행")),
        ("부동산·정책", ("부동산", "아파트", "전세", "청약", "집값", "재건축", "재개발", "국토부", "국토교통",
                       "주택", "분양", "임대", "공시가격", "오피스텔", "상가", "경매", "공매", "입주",
                       "미분양", "주담대", "주택담보", "정비사업", "LH")),
        ("경제·증시", ("증시", "코스피", "코스닥", "주가", "환율", "수출", "물가", "실적", "투자",
                       "기업", "매출", "영업이익", "로또", "경제", "금리", "원화값", "펀드")),
        ("사회·생활", ("사고", "검찰", "경찰", "재판", "의료", "교육", "수능", "날씨", "사건",
                       "논란", "지역", "병원", "화재", "부정행위", "선거", "대통령", "국회", "정부",
                       "정책", "세제", "농가", "어선", "감귤", "축제", "기탁")),
    ]
    for section, words in rules:
        if any(kw_hit(low, w) for w in words):
            return section
    return default


def collect_news() -> list[dict]:
    note("한국경제 RSS", "replaced", 0,
         "403 차단 반복 → 매일경제 · 연합뉴스 경제(둘 다 대표 이미지 포함)로 대체", kind="news")
    out: list[dict] = []
    for section, name, url, default in NEWS_FEEDS:
        for it in collect_feed(name, url, kind="news"):
            if re.match(r"\s*\[(사진|포토|화보|영상|그래픽)\]", it["title"]):
                continue  # 사진 캡션 기사는 트렌드 카드로 가치가 낮아 제외
            if is_sensitive(it["title"]):
                continue  # 애드핏·애드센스 심사에 불리한 자극적 제목은 수집 단계에서 제외
            out.append({
                "id": mk_id("n", it["title"]),
                "section": section_rules(it["title"], default),
                "feed_section": section,
                "title": it["title"],
                "source": name,
                "url": it["url"],
                "published": it["published"].isoformat() if it["published"] else "",
                "time": rel_time(it["published"]),
                "fresh": round(freshness(it["published"]), 3),
                "keywords": it["tags"][:3],
                "noise": any(h in it["title"] for h in ENTERTAINMENT_HINTS),
                "img": it.get("img", ""),
                "sample": False,
            })
    out = dedupe_items(out, key="title")
    per_section: dict[str, list[dict]] = {s: [] for s in NEWS_SECTION_ORDER}
    for n in out:
        per_section.setdefault(n["section"], []).append(n)
    balanced: list[dict] = []
    for sec in NEWS_SECTION_ORDER:
        rows = sorted(per_section.get(sec, []), key=lambda x: -x["fresh"])[:8]
        balanced.extend(rows)
    for sec, rows in per_section.items():
        if sec not in NEWS_SECTION_ORDER:
            balanced.extend(rows[:4])
    return balanced


# ----------------------------------------------------------------------------
# 3) 유튜브
# ----------------------------------------------------------------------------
# 공개 RSS 로 영상이 확인된 채널만 둡니다(각 채널 최신 5건).
YT_CHANNELS = [
    ("SBS 뉴스", "UCkinYTS9IHqOEwR1Sze2JTw"),
    ("YTN", "UChlgI3UHCOnwUGzWzbJ3H5w"),
    ("JTBC", "UCKCr4I-_ttdIhKVesomSKaQ"),
]


def clean_video_title(title: str) -> str:
    """유튜브 제목의 대괄호 태그와 채널 접미사를 정리합니다."""
    t = clean_text(title)
    t = re.sub(r"^\[[^\]]{1,14}\]\s*", "", t)          # [🔴이슈] [돌발영상] 등
    t = re.sub(r"\s*[/|]\s*(YTN|SBS|JTBC|KBS|MBC|연합뉴스TV)\s*$", "", t)
    t = re.sub(r"\s*-\s*(SBS|YTN|JTBC|KBS|MBC)(\s*뉴스)?\s*(다시보기)?\s*$", "", t)
    return re.sub(r"\s+", " ", t).strip() or clean_text(title)


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
                    "published": sn.get("publishedAt", ""),
                    "time": rel_time(_parse_dt(sn.get("publishedAt", ""))),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "img": yt_thumb(vid),
                    "sample": False,
                })
            note("YouTube Data API", "ok" if out else "skip", len(out), kind="youtube")
        except Exception as exc:  # noqa: BLE001
            note("YouTube Data API", "error", 0, str(exc), kind="youtube")

    if not out:
        for channel, cid in YT_CHANNELS:
            items = collect_feed(f"YouTube · {channel}",
                                 f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}",
                                 kind="youtube", limit=5)
            for it in items:
                vid = it.get("video_id") or yt_video_id(it.get("url", ""))
                vurl = it["url"] or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
                kind = "shorts" if "/shorts/" in (vurl or "") else "long"
                out.append({
                    "id": mk_id("y", vid or it["title"]),
                    "rank": 0,
                    "kind": kind,
                    "title": clean_video_title(it["title"]),
                    "channel": channel,
                    "views": 0,
                    "published": it["published"].isoformat() if it["published"] else "",
                    "time": rel_time(it["published"]),
                    "url": vurl,
                    # RSS media:thumbnail 이 있으면 그대로, 없으면 video_id 기반 hqdefault 로 100% 보장
                    "img": it.get("img") or yt_thumb(vid),
                    "sample": False,
                })
        # 채널별 최신 업로드 순. 쇼츠/롱폼이 섞이도록 정렬만 유지합니다.
        out.sort(key=lambda x: x.get("published", ""), reverse=True)
        for i, v in enumerate(out, 1):
            v["rank"] = i
        for i, v in enumerate(out, 1):
            v["rank"] = i
    if not out:
        note("유튜브", "skip", 0, "API 키 없음 + 채널 RSS 실패", kind="youtube")
    return out[:12]


# ----------------------------------------------------------------------------
# 4) 블로그 · 글감
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
                "desc": it["desc"][:180], "keywords": it["tags"][:3],
                "img": it.get("img", ""), "sample": False,
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
                "time": rel_time(_parse_dt(it.get("postdate", ""))),
                "desc": clean_text(it.get("description", ""))[:180],
                "keywords": [clean_text(it.get("bloggername", ""))],
                "img": it.get("image", ""), "sample": False,
            })
            n += 1
        note("네이버 블로그 API", "ok" if n else "skip", n, kind="api")
    return out[:10]


# ----------------------------------------------------------------------------
# 5) 핫딜 (네이버 쇼핑 API — 키 없으면 빈 배열, 화면은 실수집 특가 소식으로 대체)
# ----------------------------------------------------------------------------
def collect_deals() -> list[dict]:
    out: list[dict] = []
    data = _naver_api("shop", {"query": "핫딜 특가", "display": 8, "sort": "asc"})
    if data:
        for i, it in enumerate(data.get("items", [])):
            price = int(it.get("lprice", 0) or 0)
            if price <= 0:
                continue
            mall = clean_text(it.get("mallName", "") or "네이버쇼핑")
            out.append({
                "id": mk_id("d", it.get("link", it.get("title", "")) + str(i)),
                "name": clean_text(it.get("title", "")),
                "price": price,
                "store": mall,
                "url": it.get("link", ""),
                "img": it.get("image", ""),
                "sample": False,
            })
        note("네이버 쇼핑 API", "ok" if out else "skip", len(out), kind="deal")
    return out[:8]


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
            lang_m = re.search(r'itemprop="programmingLanguage">([^<]+)<', b)
            today_m = re.search(r"([\d,]+)\s+stars today", b)
            out.append({
                "id": mk_id("o", repo), "repo": repo,
                "stars": stars,
                "today": int(today_m.group(1).replace(",", "")) if today_m else 0,
                "lang": clean_text(lang_m.group(1)) if lang_m else "",
                "desc": clean_text(desc_m.group(1))[:200] if desc_m else "",
                "url": "https://github.com/" + repo,
                "img": f"https://opengraph.githubassets.com/1/{repo}",
                "sample": False,
            })
        note("GitHub Trending", "ok" if out else "skip", len(out), kind="opensource")
        return out
    except Exception as exc:  # noqa: BLE001
        note("GitHub Trending", "error", 0, str(exc), kind="opensource")
        return []


# ----------------------------------------------------------------------------
# 7) 앱 · 게임 순위
# ----------------------------------------------------------------------------
STEAM_NAMES = {730: "Counter-Strike 2", 570: "Dota 2", 578080: "PUBG: BATTLEGROUNDS",
               271590: "GTA V", 1172470: "Apex Legends", 252490: "Rust", 440: "Team Fortress 2",
               1085660: "Destiny 2", 359550: "R6 Siege", 1245620: "ELDEN RING",
               1966720: "Lethal Company", 431960: "Wallpaper Engine", 413150: "Stardew Valley",
               1091500: "Cyberpunk 2077", 292030: "The Witcher 3", 236390: "War Thunder",
               553850: "Helldivers 2", 2358720: "Black Myth: Wukong", 2246340: "Monster Hunter Wilds"}


def _apple_apps() -> list[dict]:
    """1차: iTunes JSON(앱 아이콘 포함 · 빠름), 2차: Apple 공개 RSS(아이콘 없음)."""
    try:
        data = json.loads(http_get("https://itunes.apple.com/kr/rss/topfreeapplications/limit=12/json",
                                   timeout=20))
        entries = data["feed"]["entry"]
        rows = []
        for i, e in enumerate(entries[:10], 1):
            imgs = e.get("im:image") or []
            icon = ""
            if imgs:
                icon = (imgs[-1].get("label") or "").replace("/100x100bb", "/200x200bb")
                icon = icon.replace("/170x170bb", "/200x200bb")
            rows.append({
                "id": mk_id("a", e.get("id", {}).get("label", str(i))),
                "platform": "앱스토어",
                "rank": i,
                "name": e.get("im:name", {}).get("label", ""),
                "category": (e.get("category", {}).get("attributes", {}) or {}).get("label", "앱"),
                "publisher": e.get("im:artist", {}).get("label", ""),
                "url": (e.get("id", {}) or {}).get("label", ""),
                "img": _norm_img(icon),
                "sample": False,
            })
        if rows:
            note("iTunes 앱 순위 JSON", "ok", len(rows), kind="apps")
            return rows
    except Exception as exc:  # noqa: BLE001
        note("iTunes 앱 순위 JSON", "error", 0, str(exc)[:90], kind="apps")

    try:
        data = json.loads(http_get("https://rss.applemarketingtools.com/api/v2/kr/apps/top-free/12/apps.json",
                                   timeout=25))
        rows = []
        for i, app in enumerate(data["feed"]["results"][:10], 1):
            rows.append({
                "id": mk_id("a", app.get("name", str(i))), "platform": "앱스토어",
                "rank": i, "name": app.get("name", ""),
                "category": (app.get("genres") or [{}])[0].get("name", "앱") if app.get("genres") else "앱",
                "publisher": app.get("artistName", ""), "url": app.get("url", ""),
                "img": "", "sample": False,
            })
        note("Apple 앱스토어 RSS", "ok" if rows else "skip", len(rows), kind="apps")
        return rows
    except Exception as exc:  # noqa: BLE001
        note("Apple 앱스토어 RSS", "error", 0, str(exc)[:90], kind="apps")
        return []


def collect_apps() -> list[dict]:
    out = _apple_apps()
    try:
        data = json.loads(http_get("https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/",
                                   timeout=20))
        ranks = data.get("response", {}).get("ranks", [])[:6]
        s_out = []
        for r in ranks:
            appid = r["appid"]
            s_out.append({
                "id": mk_id("g", str(appid)), "platform": "스팀 게임",
                "rank": int(r["rank"]), "name": STEAM_NAMES.get(appid, f"Steam App {appid}"),
                "category": "게임",
                "publisher": f"동시접속 {int(r.get('peak_in_game', 0)):,}",
                "url": f"https://store.steampowered.com/app/{appid}",
                "img": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg",
                "sample": False,
            })
        out.extend(s_out)
        note("Steam 최다 플레이", "ok" if s_out else "skip", len(s_out), kind="apps")
    except Exception as exc:  # noqa: BLE001
        note("Steam 최다 플레이", "error", 0, str(exc)[:90], kind="apps")
    return out


# ----------------------------------------------------------------------------
# 8) 해커톤 · 공모전
# ----------------------------------------------------------------------------
def collect_hackathons() -> list[dict]:
    try:
        data = json.loads(http_get("https://devpost.com/api/hackathons?status[]=open&order_by=deadline",
                                   timeout=20))
        out: list[dict] = []
        for h in data.get("hackathons", []):
            if len(out) >= 6:
                break
            deadline = h.get("submission_period_dates", "")
            dday = ""
            m = re.search(r"([A-Z][a-z]{2}) (\d{1,2})", deadline or "")
            if m:
                try:
                    dt = datetime.strptime(f"{m.group(1)} {m.group(2)} {now_kst().year}",
                                           "%b %d %Y").replace(tzinfo=KST)
                    if dt < now_kst() - timedelta(days=200):
                        dt = dt.replace(year=dt.year + 1)
                    dday = f"D-{max(0, (dt - now_kst()).days)}"
                except ValueError:
                    dday = ""
            name = clean_text(h.get("title", ""))
            if is_bogus_hackathon(name):
                continue  # 'test' 같은 테스트성 공모전은 목록에서 제외
            out.append({
                "id": mk_id("h", h.get("title", "")), "name": name,
                "host": clean_text(h.get("organization_name", "") or "Devpost"),
                "prize": clean_text(h.get("prize_amount", "") or ""),
                "deadline": deadline, "dday": dday or "모집중",
                "url": h.get("url", ""),
                "img": _norm_img(h.get("thumbnail_url") or ""),
                "sample": False,
            })
        note("Devpost 해커톤", "ok" if out else "skip", len(out), kind="hackathon")
        return out
    except Exception as exc:  # noqa: BLE001
        note("Devpost 해커톤", "error", 0, str(exc), kind="hackathon")
        return []


# ----------------------------------------------------------------------------
# 9) 급상승 키워드 TOP 10
# ----------------------------------------------------------------------------
def collect_trends() -> list[dict]:
    items = collect_feed("Google Trends KR", "https://trends.google.co.kr/trending/rss?geo=KR",
                         kind="trend", limit=12)
    for it in items:
        if not it.get("img"):
            it["img"] = it.get("picture", "")
        if it.get("news_url") and it.get("news_source"):
            it["source"] = it["news_source"]
    return items


# ----------------------------------------------------------------------------
# 주제 태깅 (수집 결과를 5개 주제로 분류 — 예시 데이터 없이 실제 글만)
# ----------------------------------------------------------------------------
# 제목 키워드 점수 합이 TOPIC_SCORE_MIN 이상일 때만 그 주제로 넣습니다.
#   core(2점) = 그 주제 자체를 가리키는 말 / weak(1점) = 문맥을 보태는 말
# 예전에는 제목에 '정부·공사·도시·모델' 같은 넓은 단어가 하나만 있어도 태그가 붙고,
# 뉴스 분야(section)를 그대로 주제로 옮겨서 무관한 기사가 부동산·경매 탭에 들어갔습니다.
TOPIC_RULES = {
    "mom": {
        "core": ("숲놀이", "유아", "육아", "어린이집", "유치원", "초등학생", "학부모", "보육", "급식",
                 "돌봄", "아동", "방학", "키즈", "숲 체험", "숲체험", "엄마표"),
        "weak": ("숲", "초등", "엄마", "아이", "교사", "놀이"),
    },
    "estate": {
        "core": ("부동산", "아파트", "전세", "월세", "청약", "분양", "재건축", "재개발", "경매", "공매",
                 "낙찰", "집값", "전셋값", "매매가", "임대", "주택", "국토부", "국토교통", "LH", "주담대",
                 "모기지", "오피스텔", "상가", "토지", "공시가격", "입주", "미분양", "한국부동산원",
                 "공인중개사", "정비사업", "아파트값", "전세사기", "갭투자", "주택담보", "전세대출"),
        "weak": ("기준금리", "보유세", "종부세", "취득세", "재산세", "분양가", "청약통장", "임대차",
                 "도시재생", "땅값", "주거", "세입자", "집주인", "용적률", "건폐율"),
    },
    "ai": {
        "core": ("인공지능", "AI", "챗GPT", "챗gpt", "생성형", "LLM", "오픈AI", "앤트로픽", "제미나이",
                 "클로드", "엔비디아", "GPU", "반도체", "데이터센터", "로봇", "머신러닝", "딥러닝",
                 "자율주행", "AI 에이전트", "코파일럿", "허깅페이스", "파운데이션 모델"),
        "weak": ("알고리즘", "자동화", "챗봇", "빅데이터", "클라우드", "디지털 전환"),
    },
    "apptech": {
        "core": ("핫딜", "특가", "쿠폰", "앱테크", "리워드", "최저가", "블랙프라이데이", "반값", "경품",
                 "체험단", "무료배송", "할인코드", "기프티콘", "포인트 적립", "리퍼브"),
        "weak": ("할인", "포인트", "구독", "무료", "이벤트", "프로모션", "세일"),
    },
    "build": {
        "core": ("건축", "설계", "입찰", "나라장터", "시공", "감리", "인테리어", "용역", "리모델링",
                 "조경", "철골", "안전진단", "공사비", "BIM", "구조설계", "도급", "하도급", "현상설계",
                 "건설사", "설계공모", "공모전"),
        "weak": ("도시", "공사", "건설", "용적률", "건폐율", "공정률"),
    },
}
TOPIC_SCORE_MIN = 2


def topic_tags(text: str, section: str = "") -> list[str]:
    """제목 키워드 점수로 주제 태그를 만듭니다(수집 글만 대상 · 예시 없음).

    section 은 더 이상 주제를 강제하지 않습니다(참고용 인자만 유지).
    """
    low = text.lower()
    hits: list[str] = []
    for cat, rules in TOPIC_RULES.items():
        if cat == "estate" and is_accident(text) and not any(kw_hit(low, w) for w in ESTATE_MARKET_HINTS):
            continue  # 화재·사고 기사는 부동산·경매 주제로 넣지 않습니다
        score = 0
        for w in rules.get("core", ()):
            if kw_hit(low, w):
                score += 2
        for w in rules.get("weak", ()):
            if kw_hit(low, w):
                score += 1
        if score >= TOPIC_SCORE_MIN:
            hits.append(cat)
    return hits


# ----------------------------------------------------------------------------
# 자극적·선정적 제목 필터 (애드핏·애드센스 심사 감점 위험 · 수집·빌드 공통 원칙)
# ----------------------------------------------------------------------------
SENSITIVE_PATTERNS = (
    r"불륜", r"외도", r"성폭행", r"성폭력", r"강간", r"성추행", r"성희롱", r"성매매", r"성범죄",
    r"음란", r"야동", r"포르노", r"성관계", r"자살", r"자해", r"살인", r"살해", r"시신", r"시체",
    r"변사체", r"마약", r"도박", r"폭행", r"폭력", r"구타", r"혐오", r"범죄자", r"몰카", r"나체",
    r"정사신", r"원조교제", r"미성년자.*성",
)
SENSITIVE_PAIRS = (
    ("산부인과", "여환자"), ("산부인과", "당황"), ("부부", "성생활"), ("성인", "영상"),
)
SENSITIVE_RE = re.compile("|".join(SENSITIVE_PATTERNS), re.I)


def is_sensitive(title: str, desc: str = "") -> bool:
    """제목·요약에 선정적·자극적 표현이 있으면 True."""
    t = f"{title or ''} {desc or ''}"
    if SENSITIVE_RE.search(t):
        return True
    return any(a in t and b in t for a, b in SENSITIVE_PAIRS)


# 무의미한 테스트성 해커톤(예: name='test')은 공모전 목록에서 뺍니다.
TEST_HACKATHON_NAMES = {"test", "test1", "test2", "testing", "테스트", "테스트1", "sample",
                        "demo", "asdf", "aaa", "aaaa", "untitled", "hackathon", "my hackathon",
                        "new hackathon"}


def is_bogus_hackathon(name: str) -> bool:
    n = re.sub(r"\s+", " ", str(name or "")).strip().lower()
    if not n:
        return True
    if n in TEST_HACKATHON_NAMES:
        return True
    if re.fullmatch(r"(test|테스트|sample|demo|asdf|qwer|aaa+|123+)[\s\-_0-9]*", n):
        return True
    return len(re.sub(r"[^0-9a-z가-힣]", "", n)) < 3


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


def score_posts(items: list[dict]) -> None:
    """인기(hot) 0~100 · 급상승(rise) % 추정치 (최신성 + 반응)."""
    for it in items:
        f = it.get("fresh", 0.5)
        comments = it.get("comments", 0)
        views = it.get("views", 0)
        engagement = min(1.0, (comments / 150.0) * 0.6 + (views / 6000.0) * 0.4)
        base = 0.6 * f + 0.4 * engagement if (comments or views) else 0.55 * f + 0.15
        it["hot"] = int(round(30 + min(1.0, base) * 68))
        it["rise"] = int(round(80 + min(1.0, base) * 300))
        it.pop("fresh", None)


def build_ranks(feed_items: list[dict], trends: list[dict]) -> dict:
    """TOP 10 급상승 키워드. Google Trends 실시간 + 수집 제목 키워드 빈도를 합쳐 정렬합니다.

    Google Trends KR 은 스포츠 경기 대진(‘A 대 B’)이 많이 섞여 나오므로 감점하고,
    실제 수집 제목에서 자주 등장한 키워드를 함께 올립니다.
    """
    rows: list[dict] = []
    seen: set[str] = set()

    def kw_image(keyword: str) -> str:
        for item in feed_items:
            if keyword and keyword.lower() in (item.get("title") or "").lower():
                if item.get("img"):
                    return item["img"]
        return ""

    for t in trends:
        k = clean_text(t["title"])[:28]
        if not k or k.lower() in seen:
            continue
        # 수집 기사에 없는 외국어(라틴) 인명·구단명만 있는 항목은 제외
        if not re.search(r"[가-힣]", k) and not kw_image(k):
            continue
        num = 0
        m = re.search(r"([\d,]+)", t.get("traffic") or "")
        if m:
            num = int(m.group(1).replace(",", ""))
        r = min(999, 160 + int(num / 25)) if num else 180
        # 스포츠 대진·해외 인물명 위주 항목은 감점
        if re.search(r"\s대\s", k) or re.search(r"\bvs\b", k, re.I):
            r -= 80
        # 수집된 기사·영상 제목에 없는 키워드는 관련도 감점
        if not kw_image(k):
            r -= 40
        rows.append({"k": k, "r": max(60, r), "url": t.get("news_url") or "",
                     "img": t.get("img", "") or kw_image(k), "src": t.get("source", "Google Trends")})
        seen.add(k.lower())

    KEYWORD_NOISE = {"GeekNews", "AI·개발", "유튜브", "long", "shorts", "실시간뉴스",
                     "구글뉴스", "나라장터", "건축설계", "종합", "속보", "헤드라인", "기자",
                     "오늘", "내년", "이번", "관련", "발표", "공개", "우리", "지금",
                     "사진", "영상", "기사", "단독", "인터뷰", "현장", "확인", "가능성",
                     "예정", "내일", "모두", "위해", "대한", "따라", "지난", "올해", "경우",
                     "때문", "라며", "밝혀", "전해", "나타", "이어", "이날", "당시", "논란",
                     "진짜", "이슈", "실시간", "라이브", "뉴스", "오늘의", "주요", "핵심",
                     "출시", "첫날", "예고", "돌입", "개최", "선정", "돌파", "급등", "급락",
                     "논의", "추진", "확정", "판매", "인상", "인하", "기록", "상승", "하락",
                     "공급", "전망", "강조", "요청", "마련", "점검"}
    # 매체명·채널명은 키워드가 아니므로 제외
    src_noise: set[str] = set()
    for item in feed_items:
        s = clean_text(item.get("source") or "")
        if s:
            src_noise.add(s.lower())
            for w in re.findall(r"[가-힣A-Za-z0-9]{2,12}", s):
                src_noise.add(w.lower())
    src_noise |= {"ytn", "sbs", "jtbc", "sbs 뉴스", "유튜브", "네이트판", "더쿠", "보배드림",
                  "82cook", "매일경제", "연합뉴스", "전자신문", "ai타임스", "조선일보",
                  "geeknews", "슬로우뉴스", "바이라인네트워크"}

    counter: dict[str, float] = {}
    for item in feed_items:
        title = item.get("title", "")
        for tag in (item.get("keywords") or []):
            tag = clean_text(tag)
            if (1 < len(tag) <= 14 and tag not in KEYWORD_NOISE
                    and tag.lower() not in src_noise):
                counter[tag] = counter.get(tag, 0) + 1.2
        for w in re.findall(r"[가-힣A-Za-z0-9]{2,12}", title):
            if w in KEYWORD_NOISE or w.lower() in src_noise or w.isdigit():
                continue
            if len(w) <= 3 and w[-1] in "엔는을를이가은도게만에로와과의":
                continue
            counter[w] = counter.get(w, 0) + 0.6

    for k, v in sorted(counter.items(), key=lambda x: -x[1])[:30]:
        if len(rows) >= 22:
            break
        if k.lower() in seen or k.lower() in src_noise:
            continue
        rows.append({"k": k, "r": int(min(420, 120 + v * 24)), "url": "",
                     "img": kw_image(k), "src": "트렌드픽 수집"})
        seen.add(k.lower())

    rows.sort(key=lambda x: -x["r"])
    return {"all": rows[:10], "updated_at": now_kst().isoformat(timespec="seconds")}


# ----------------------------------------------------------------------------
# 브리프 (규칙 기반 — 키 없이도 완성)
# ----------------------------------------------------------------------------
def news_importance(n: dict) -> float:
    section_weight = {"경제·증시": 1.0, "IT·AI": 0.96, "부동산·정책": 0.94, "사회·생활": 0.8}
    score = section_weight.get(n.get("section", ""), 0.6)
    if any(s in n.get("source", "") for s in PREFERRED_SOURCES):
        score += 0.18
    if any(h in n.get("title", "") for h in ENTERTAINMENT_HINTS):
        score -= 0.55
    if len(n.get("title", "")) < 12:
        score -= 0.1
    score += n.get("fresh", 0.5) * 0.2
    return score


TOPIC_PLAN = [("mom", "맘카페·육아", "🌿"), ("estate", "부동산·경매", "🏢"),
              ("ai", "AI·부업", "🤖"), ("apptech", "앱테크·핫딜", "💰"),
              ("build", "건축·입찰", "📐")]


def rule_brief(news: list[dict], feed: list[dict], issue_no: int) -> dict:
    ranked = sorted(news, key=lambda n: -news_importance(n))
    by_section: dict[str, list[dict]] = {}
    for n in ranked:
        by_section.setdefault(n["section"], []).append(n)

    sections: list[dict] = []
    for section in NEWS_SECTION_ORDER:
        items = by_section.get(section, [])[:3]
        if not items:
            continue
        sources: list[str] = []
        for i in items:
            if i["source"] not in sources:
                sources.append(i["source"])
        lead = items[0]["title"]
        body = f"{'·'.join(sources[:3])} 등이 전한 {section} 흐름입니다. {lead}"
        if len(items) > 1:
            body += " 이어서 " + ", ".join(f"'{i['title'][:40]}'" for i in items[1:]) + "도 함께 다뤄졌습니다."
        sections.append({
            "key": section, "label": section, "emoji": "📰", "title": lead[:90], "body": body[:420],
            "points": [{"text": f"{i['title'][:60]}", "source": i["source"], "url": i.get("url", "")}
                       for i in items],
        })

    # 실제 수집 글에서 주제별 대표 1~2건 (이미 뉴스 섹션에 나온 글은 제외)
    used_titles = {p["text"] for s in sections for p in s["points"]}
    for cat, label, emoji in TOPIC_PLAN:
        rows = [p for p in feed if cat in (p.get("topics_kw") or [])
                and p["title"][:60] not in used_titles][:2]
        if not rows:
            continue
        used_titles.update(r["title"][:60] for r in rows)
        sections.append({
            "key": cat, "label": label, "emoji": emoji,
            "title": rows[0]["title"][:90],
            "body": (f"{rows[0]['source']}에서 '{rows[0]['title'][:56]}' 글이 올라왔습니다."
                     + (f" {rows[1]['source']}에서도 비슷한 흐름의 글이 함께 수집됐습니다."
                        if len(rows) > 1 else "")),
            "points": [{"text": r["title"][:60], "source": r["source"], "url": r.get("url", "")}
                       for r in rows],
        })

    if not sections:
        sections = [{"key": "comm", "label": "커뮤니티", "emoji": "💬",
                     "title": "오늘 수집된 인기글", "body": "수집 결과가 적은 날입니다.",
                     "points": [{"text": p["title"][:50], "source": p["source"], "url": p.get("url", "")}
                                for p in feed[:3]]}]

    picks = []
    used_sections: set[str] = set()
    for n in ranked:
        if len(picks) >= 5:
            break
        if n["section"] in used_sections:
            continue
        used_sections.add(n["section"])
        picks.append({"rank": len(picks) + 1, "label": n["section"], "title": n["title"],
                      "source": n["source"], "url": n.get("url", ""), "img": n.get("img", "")})
    for n in ranked:  # 분야가 모자란 날은 같은 분야로 채움 (첫 항목 = 대표 헤드라인, 나머지 = 핫픽 3선)
        if len(picks) >= 5:
            break
        if any(p["title"] == n["title"] for p in picks):
            continue
        picks.append({"rank": len(picks) + 1, "label": n["section"], "title": n["title"],
                      "source": n["source"], "url": n.get("url", ""), "img": n.get("img", "")})

    heads = [x["title"] for x in sections[:3]]
    labels = [x["label"] for x in sections[:4]]
    lead = ""
    if heads:
        # 첫 항목은 화면 상단 헤드라인으로 쓰이므로, 본문은 2·3번 이슈로 요약합니다.
        parts = []
        if len(heads) > 1:
            second = heads[1][:26] + ("…" if len(heads[1]) > 26 else "")
            parts.append(f"{sections[1]['label']}에서는 '{second}' 흐름이 이어졌습니다")
        if len(heads) > 2:
            third = heads[2][:24] + ("…" if len(heads[2]) > 24 else "")
            parts.append(f"{sections[2]['label']} 쪽에서도 '{third}' 소식이 눈에 띕니다")
        lead = ". ".join(parts) + ". " if parts else ""
        lead += f"오늘 수집한 {len(news) + len(feed)}건에서 {'·'.join(dict.fromkeys(labels))} 분야 {len(sections)}개 이슈를 골랐습니다."

    return {
        "no": f"No.{issue_no:02d}",
        "date": now_kst().strftime("%Y-%m-%d"),
        "label": now_kst().strftime("%m.%d"),
        "weekday": "월화수목금토일"[now_kst().weekday()],
        "title": " · ".join(h[:34] for h in heads[:3]) or "오늘의 트렌드픽 브리프",
        "lead": lead[:600],
        "picks": picks,
        "metrics": {"topics": len(sections), "news": len(news), "items": len(feed) + len(news)},
        "sections": sections[:6],
        "engine": "rule-based",
        "past": [],
    }


def attach_history(payload: dict) -> None:
    """오늘 브리프를 data/history/YYYY-MM-DD.json 으로 남기고 최근 5회를 지난 호로 붙입니다."""
    hist_dir = ROOT / "data" / "history"
    hist_dir.mkdir(parents=True, exist_ok=True)
    today = now_kst().strftime("%Y-%m-%d")
    snap = {"date": today, "issue": payload.get("issue"), "generated_at": payload.get("generated_at"),
            "brief": payload.get("brief"), "stats": payload.get("stats"),
            "ranks": (payload.get("ranks") or {}).get("all")}
    (hist_dir / f"{today}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

    past = []
    for f in sorted(hist_dir.glob("????-??-??.json"), reverse=True):
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


def thumb_stats(payload: dict) -> dict:
    groups = {
        "news": payload.get("news", []),
        "community": payload.get("posts", []),
        "youtube": payload.get("videos", []),
        "blog": payload.get("blogs", []),
        "deals": payload.get("deals", []),
        "opensource": payload.get("opensource", []),
        "apps": payload.get("apps", []),
        "hackathons": payload.get("hackathons", []),
    }
    out = {}
    total = have = 0
    for name, rows in groups.items():
        n = len(rows)
        m = sum(1 for r in rows if r.get("img"))
        out[name] = {"total": n, "with_image": m,
                     "rate": round(m / n, 3) if n else 0.0}
        total += n
        have += m
    out["all"] = {"total": total, "with_image": have,
                  "rate": round(have / total, 3) if total else 0.0}
    return out


def build_payload() -> dict:
    started = time.time()
    log("수집 시작 · 트렌드픽 v3")
    issue_no = issue_number()

    # --- 커뮤니티
    posts: list[dict] = []
    for name, url, key, pattern in COMMUNITY_SCRAPE:
        for r in scrape_community(name, url, key, pattern):
            posts.append({
                "id": mk_id("c", r["title"]),
                "cat": "comm", "source": name, "source_key": key,
                "title": r["title"], "url": r["url"],
                "published": "", "time": "최근",
                "img": r.get("img", ""),
                "keywords": [name], "sample": False,
                "fresh": 0.62,
            })
    posts = dedupe_items(posts)[:16]

    # --- 뉴스 · 유튜브 · 블로그 · 핫딜 · 오픈소스 · 앱 · 해커톤
    news = collect_news()
    videos = collect_youtube()
    blogs = collect_blogs()
    deals = collect_deals()
    opensource = collect_opensource()
    apps = collect_apps()
    hackathons = collect_hackathons()
    trends = collect_trends()

    # --- 통합 피드용 뉴스 카드
    for i, n in enumerate(news):
        n["cat"] = "news"
        n["hot"] = max(40, 88 - i)
        n["rise"] = max(90, 260 - i * 6)
        n["comments"] = 0
        n["views"] = 0
        n["sample"] = False

    for v in videos:
        v["cat"] = "youtube"
        v["source"] = v.get("channel", "YouTube")
        v["hot"] = max(42, 78 - int(v.get("rank", 50)))
        v["rise"] = max(95, 250 - int(v.get("rank", 50)) * 5)
        v["comments"] = 0
        v["time"] = v.get("time") or "최근"
        v["keywords"] = ["유튜브", v.get("kind", "long")]

    for b in blogs:
        b["cat"] = "web"
        b["hot"] = 62
        b["rise"] = 140
        b["sample"] = False

    # --- 주제 태깅 + og:image 보강 (이미지 없는 항목만)
    all_items = posts + news + videos + blogs
    for it in all_items:
        text = it.get("title", "") + " " + (it.get("source") or "")
        it["topics_kw"] = topic_tags(it.get("title", ""))
        it["topics"] = topic_tags(text)
    enrich_images([it for it in all_items if not it.get("img")], budget_sec=45.0, workers=8, limit=50)

    score_posts(posts)
    all_items.sort(key=lambda x: -x.get("hot", 0))

    visited_sources = ({p["source"] for p in posts} | {n["source"] for n in news}
                       | {v.get("channel", "YouTube") for v in videos} | {b["source"] for b in blogs}
                       | {o["repo"].split("/")[0] for o in opensource})
    stats = {
        "sources": len(visited_sources),
        "collected": len(all_items) + len(deals) + len(opensource) + len(apps) + len(hackathons),
        "live_sources": sum(1 for r in COLLECT_LOG if r["status"] == "ok"),
        "skipped_sources": sum(1 for r in COLLECT_LOG if r["status"] in ("skip", "error", "key-missing")),
        "elapsed_sec": round(time.time() - started, 1),
    }

    brief = rule_brief(news, all_items, issue_no)
    payload = {
        "schema": SCHEMA,
        "generated_at": now_kst().isoformat(timespec="seconds"),
        "issue": {"no": issue_no, "label": f"No.{issue_no:02d} ({now_kst():%m.%d})",
                  "date": now_kst().strftime("%Y-%m-%d")},
        "stats": stats,
        "sources": sorted(visited_sources),
        "youtube_mode": "api" if os.environ.get("YOUTUBE_API_KEY", "").strip() else "channel-rss",
        "site": {
            "repo": os.environ.get("GITHUB_REPOSITORY", "").strip() or "econature7-lab/nori-traffic-scent",
            "pages_url": (("https://" + os.environ.get("GITHUB_REPOSITORY", "econature7-lab/nori-traffic-scent")
                           .split("/")[0].lower() + ".github.io/"
                           + os.environ.get("GITHUB_REPOSITORY", "econature7-lab/nori-traffic-scent")
                           .split("/")[-1] + "/")
                          if os.environ.get("GITHUB_REPOSITORY", "").strip()
                          else "https://econature7-lab.github.io/nori-traffic-scent/"),
        },
        "posts": posts,
        "news": news,
        "videos": videos,
        "blogs": blogs,
        "deals": deals,
        "opensource": opensource,
        "apps": apps,
        "hackathons": hackathons,
        "ranks": build_ranks(all_items, trends),
        "brief": brief,
        "collect_log": COLLECT_LOG,
        "notes": [
            "posts/news/videos/blogs 는 모두 공개 RSS·API 에서 실제로 수집한 항목입니다(예시 데이터 없음).",
            "rise 값은 최신성·반응을 합산한 상승 지수 추정치입니다.",
            "이미지가 없는 항목은 화면에서 카테고리 일러스트 카드로 대체됩니다.",
        ],
    }
    payload["thumbs"] = thumb_stats(payload)
    attach_history(payload)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="트렌드픽 v3 수집기")
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
    th = payload["thumbs"]
    log(f"썸네일: 전체 {th['all']['with_image']}/{th['all']['total']} ({th['all']['rate'] * 100:.0f}%) · "
        f"유튜브 {th['youtube']['with_image']}/{th['youtube']['total']} · "
        f"뉴스 {th['news']['with_image']}/{th['news']['total']}")
    ok = sum(1 for r in payload["collect_log"] if r["status"] == "ok")
    skip = sum(1 for r in payload["collect_log"] if r["status"] in ("skip", "error"))
    keyless = sum(1 for r in payload["collect_log"] if r["status"] == "key-missing")
    log(f"소스 상태: 성공 {ok} · 건너뜀/실패 {skip} · 키 미설정 {keyless}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
