#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
트렌드픽 TrendPick v3 · summarize.py
===================================
collector.py 가 만든 data.json 을 읽어
  1) DAILY BRIEF(일간 트렌드 리포트) — 핵심 흐름 + 이슈별 포인트를 짚는 2~3문단 해설
  2) 상위 인기글 한 줄 요약
을 채워 넣습니다.

- GEMINI_API_KEY 가 있으면 Gemini Flash 무료 티어 REST API 호출 (PC 클로드 한도 미사용)
- 키가 없거나 호출이 실패하면 **규칙 기반 브리프로 대체**하고도 data.json 은 정상 생성
  (규칙 기반도 2~3문단 해설 + 분야별 본문 + 핵심 포인트 3줄까지 만듭니다)
- 어떤 경우에도 스크립트가 0이 아닌 코드로 끝나 GitHub Actions 를 깨뜨리지 않습니다.

brief 구조
  title       편집 헤드라인 (한 줄)
  lead        화면 상단 1~2문장 요약
  paragraphs  본문 2~3문단 (브리프 전문 영역에 그대로 실립니다)
  highlights  핵심 포인트 3개 {label, text, url, source}
  sections    분야별 카드 {key, label, emoji, title, body, points[]}
  picks       대표 기사 (collector.py 가 만든 값 유지)
  metrics     수집 수치 (collector.py 가 만든 값 유지)

사용법
  python summarize.py                 # data.json 제자리 갱신
  python summarize.py --dry-run       # API 호출 없이 규칙 브리프만
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data.json"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
FALLBACK_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash"]
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

NEWS_SECTION_ORDER = ["경제·증시", "IT·AI", "부동산·정책", "사회·생활"]
SECTION_KEY = {"경제·증시": ("econ", "📈"), "IT·AI": ("ai", "🤖"),
               "부동산·정책": ("estate", "🏢"), "사회·생활": ("social", "🧾")}
TOPIC_PLAN = [("mom", "맘카페·육아", "🌿"), ("estate", "부동산·경매", "🏢"),
              ("ai", "AI·부업", "🤖"), ("apptech", "앱테크·핫딜", "💰"),
              ("build", "건축·입찰", "📐")]
# 브리프 '챙겨볼 것' 문단에서 쓰는 분야 순서
TOPIC_LABEL = {k: label for k, label, _ in TOPIC_PLAN}


def log(msg: str) -> None:
    print(f"[{datetime.now(KST):%H:%M:%S}] {msg}", flush=True)


# --------------------------------------------------------------- 공통 유틸
def clean(t: str) -> str:
    s = re.sub(r"\s+", " ", str(t or "")).strip()
    # 급상승 키워드에 섞이는 '12 월 3 일' 같은 자동 띄어쓰기를 바로잡습니다
    return re.sub(r"(\d)\s+(월|일|년|주|개|건|명|분|초)", r"\1\2", s)


def short(t: str, n: int) -> str:
    t = clean(t)
    return t if len(t) <= n else t[: n - 1].rstrip(" ,·…") + "…"


def quote(t: str, n: int) -> str:
    """제목을 큰따옴표 없이 감쌉니다. 안쪽 따옴표는 지워 문장이 겹따옴표로 엉키지 않게 합니다."""
    inner = re.sub(r"[‘’“”\"']", "", clean(t))
    return f"‘{short(inner, n)}’"


def line_break(t: str, n: int) -> str:
    """따옴표 없이 제목만 짧게 (따옴표 남발을 피하는 문장용)"""
    return short(re.sub(r"[‘’“”\"']", "", clean(t)), n)


def sources(items: list[dict], limit: int = 3) -> list[str]:
    out: list[str] = []
    for i in items:
        s = clean(i.get("source") or i.get("channel") or "")
        if s and s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def key_of(title: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(title or ""))[:40].lower()


def count_items(data: dict) -> int:
    """화면에 표시되는 수집 수(기사 + 커뮤니티·영상·블로그) — brief.metrics 와 같은 기준."""
    metrics = (data.get("brief") or {}).get("metrics") or {}
    if metrics.get("items"):
        return int(metrics["items"])
    news = len([n for n in (data.get("news") or []) if not n.get("noise")])
    feed = sum(len(data.get(k) or []) for k in ("posts", "videos", "blogs"))
    return news + feed + news


# --------------------------------------------------------------- 규칙 기반
def rule_sections(data: dict) -> list[dict]:
    """수집된 제목만으로 분야별 카드를 만듭니다. 해설은 '무엇이 함께 나왔는지'까지만 씁니다."""
    news = [n for n in (data.get("news") or []) if not n.get("noise")]
    posts = data.get("posts") or []
    by_section: dict[str, list[dict]] = {}
    for n in news:
        by_section.setdefault(clean(n.get("section")) or "뉴스", []).append(n)

    sections: list[dict] = []
    for name in NEWS_SECTION_ORDER + [s for s in by_section if s not in NEWS_SECTION_ORDER]:
        items = by_section.get(name) or []
        if not items:
            continue
        items = items[:3]
        key, emoji = SECTION_KEY.get(name, ("news", "📰"))
        head = items[0]
        srcs = sources(items)
        body = f"{name}에서는 {quote(head.get('title', ''), 52)} 보도가 가장 먼저 눈에 들어옵니다."
        if len(items) > 1:
            body += " 같은 분야에서 " + ", ".join(quote(i.get("title", ""), 40) for i in items[1:]) + "도 함께 올라왔습니다."
        if srcs:
            body += f" {', '.join(srcs)} 등이 전한 소식입니다."
        sections.append({
            "key": key, "label": name, "emoji": emoji,
            "title": short(head.get("title", ""), 70),
            "body": body,
            "points": [
                {"text": short(i.get("title", ""), 52),
                 "source": clean(i.get("source")), "url": i.get("url", ""),
                 "title": i.get("title", "")}
                for i in items
            ],
        })

    # 특화 분야: 뉴스에 안 잡힌 커뮤니티·블로그 글 중 주제 태그가 붙은 것
    used = {key_of(p["title"]) for s in sections for p in s["points"]}
    for cat, label, emoji in TOPIC_PLAN:
        rows = [p for p in posts
                if cat in (p.get("topics_kw") or []) and key_of(p.get("title", "")) not in used][:2]
        if not rows:
            continue
        used.update(key_of(r.get("title", "")) for r in rows)
        head = rows[0]
        body = (f"{clean(head.get('source')) or '커뮤니티'}에서 {quote(head.get('title', ''), 48)} 글이 올라왔습니다.")
        if len(rows) > 1:
            body += f" {clean(rows[1].get('source')) or '다른 곳'}에서도 비슷한 주제의 글이 함께 수집됐습니다."
        sections.append({
            "key": cat, "label": label, "emoji": emoji,
            "title": short(head.get("title", ""), 70),
            "body": body,
            "points": [
                {"text": short(r.get("title", ""), 52), "source": clean(r.get("source")),
                 "url": r.get("url", ""), "title": r.get("title", "")}
                for r in rows
            ],
        })
    return sections[:6]


def rule_paragraphs(data: dict, sections: list[dict]) -> list[str]:
    """수집 제목·수치만으로 쓰는 2~3문단 해설. 없는 사실은 만들지 않습니다."""
    news = [n for n in (data.get("news") or []) if not n.get("noise")]
    total = count_items(data)
    stats = data.get("stats") or {}
    src_n = stats.get("live_sources") or stats.get("sources") or 0
    issue = data.get("issue") or {}
    paras: list[str] = []

    # 1문단 — 오늘의 핵심 흐름 (조사가 따옴표에 붙지 않도록 '소식/보도'를 붙여 씁니다)
    p1: list[str] = []
    if sections:
        first = sections[0]
        p1.append(f"오늘 수집한 {total}건에서 가장 먼저 붙잡은 흐름은 {first['label']}입니다. "
                  f"{quote(first['title'], 44)} 소식이 이 분야의 머리를 열었습니다.")
        if len(sections) > 1:
            second = sections[1]
            p1.append(f"{second['label']} 쪽에서는 {quote(second['title'], 40)} 보도가 바로 뒤를 이었습니다.")
        if len(sections) > 2:
            third = sections[2]
            p1.append(f"{third['label']}에서는 {quote(third['title'], 36)} 소식이 세 번째 축으로 잡혔습니다.")
        tail = []
        if src_n:
            tail.append(f"출처 {src_n}곳")
        tail.append(f"기사 {len(news)}건과 커뮤니티·영상·블로그 글을 같은 기준으로 묶었습니다")
        p1.append("에서 모은 ".join(tail) + "." if src_n else " ".join(tail) + ".")
    paras.append(" ".join(p1) if p1 else f"오늘은 수집된 소식이 적은 날입니다. 모인 {total}건을 분야별로 정리했습니다.")

    # 2문단 — 이슈별 포인트 (분야별 한 문장, 문장 틀을 돌려가며 씀)
    p2: list[str] = []
    frames = [
        "{label}에서는 {q1} 소식이 가장 눈에 띄고, {q2}도 함께 올라왔습니다.",
        "{label}는 {q1} 보도와 {q2} 기사가 나란히 잡혔습니다.",
        "{label} 쪽은 {q1} 소식이 중심이고, {q2}도 같이 볼 만합니다.",
        "{label}에서는 {q1}를 비롯해 {q2}까지 한 묶음으로 수집됐습니다.",
    ]
    for i, s in enumerate(sections[:4]):
        pts = [p for p in (s.get("points") or []) if clean(p.get("text"))]
        if not pts:
            continue
        q1 = quote(pts[0]["text"], 26)
        if len(pts) > 1:
            q2 = quote(pts[1]["text"], 22)
            p2.append(frames[i % len(frames)].format(label=s["label"], q1=q1, q2=q2))
        else:
            p2.append(f"{s['label']}에서는 {q1} 소식 한 건이 눈에 띕니다.")
    keywords = [clean(r.get("k")) for r in ((data.get("ranks") or {}).get("all") or [])[:5]]
    keywords = [k for k in keywords if k]
    if keywords:
        p2.append("오늘 급상승 키워드는 " + ", ".join(f"‘{k}’" for k in keywords)
                  + " 순으로 올라왔습니다. 기사 제목만으로는 잘 안 잡히는 관심이 여기 먼저 나타납니다.")
    paras.append(" ".join(p2) if p2 else "분야별 대표 소식이 아직 충분히 모이지 않았습니다.")

    # 3문단 — 오늘 챙겨볼 것
    p3: list[str] = []
    videos = [v for v in (data.get("videos") or []) if v.get("title")][:2]
    if videos:
        v0 = videos[0]
        if v0.get("views"):
            p3.append(f"영상은 {quote(v0.get('title', ''), 30)} — 조회 {int(v0['views']):,}회로 가장 앞섰습니다.")
        else:
            p3.append(f"영상은 {quote(v0.get('title', ''), 30)}가 가장 먼저 눈에 띄었습니다.")
        if len(videos) > 1:
            p3.append(f"{quote(videos[1].get('title', ''), 24)}도 함께 올라왔습니다.")
    apps = [a for a in (data.get("apps") or []) if a.get("rank") and a.get("platform")]
    if apps:
        tops: dict[str, dict] = {}
        for a in apps:
            plat = clean(a.get("platform"))
            if plat not in tops or (a.get("rank") or 999) < (tops[plat].get("rank") or 999):
                tops[plat] = a
        p3.append("앱·게임 순위는 " + ", ".join(
            f"{plat} 1위 {clean(a.get('name'))}" for plat, a in list(tops.items())[:2]
        ) + "로 집계됐습니다.")
    hacks = [h for h in (data.get("hackathons") or []) if h.get("dday")]
    zero = [h for h in hacks if clean(h.get("dday")).upper().replace(" ", "") in ("D-0", "D-DAY", "D-0일")]
    if zero:
        p3.append(f"오늘 마감인 해커톤·공모전이 {len(zero)}건 있으니 지원을 준비 중이라면 일정부터 확인하세요.")
    elif hacks:
        p3.append(f"마감이 가까운 공모전은 {quote(hacks[0].get('name', ''), 30)} ({clean(hacks[0].get('dday'))})입니다.")
    if not p3:
        p3.append("오늘은 영상·앱·공모전 쪽에 새로 눈에 띈 항목이 적었습니다. 다음 수집에서 다시 채워집니다.")
    paras.append(" ".join(p3))
    return paras


def rule_highlights(sections: list[dict]) -> list[dict]:
    out = []
    for s in sections[:3]:
        pt = (s.get("points") or [{}])[0]
        out.append({"label": s.get("label", ""), "text": clean(s.get("title") or pt.get("text") or ""),
                    "url": pt.get("url", ""), "source": pt.get("source", "")})
    return out


def rule_title(sections: list[dict]) -> str:
    if not sections:
        return "오늘의 트렌드픽 브리프"
    head = line_break(sections[0]["title"], 38)
    if len(sections) > 1 and len(head) < 24:
        head += " 외"
    return head


def rule_lead(data: dict, sections: list[dict], paragraphs: list[str]) -> str:
    """덱(1~2문장) — 1문단과 겹치지 않게 '무엇을 얼마나 묶었는지' 중심으로 씁니다."""
    news = len([n for n in (data.get("news") or []) if not n.get("noise")])
    feed = sum(len(data.get(k) or []) for k in ("posts", "videos", "blogs"))
    issue = data.get("issue") or {}
    if not sections and not news:
        return "오늘 수집한 소식을 분야별로 정리했습니다."
    head = f"{issue['date']} 기준 " if issue.get("date") else ""
    body = f"기사 {news}건과 커뮤니티·영상·블로그 {feed}건을 {len(sections)}개 분야로 나눴습니다."
    tail = ""
    if len(sections) > 1:
        tail = f" 가장 큰 흐름은 {sections[0]['label']}, 그다음은 {sections[1]['label']}입니다."
    elif sections:
        tail = f" 가장 큰 흐름은 {sections[0]['label']}입니다."
    return head + body + tail


def rule_brief(data: dict) -> dict:
    sections = rule_sections(data)
    paragraphs = rule_paragraphs(data, sections)
    return {
        "title": rule_title(sections),
        "lead": rule_lead(data, sections, paragraphs),
        "paragraphs": paragraphs,
        "highlights": rule_highlights(sections),
        "sections": sections,
        "post_summaries": {},
        "engine": "rule-based",
    }


# --------------------------------------------------------------- Gemini
def build_prompt(data: dict) -> str:
    news = [n for n in (data.get("news") or []) if not n.get("noise")][:26]
    posts = (data.get("posts") or [])[:14]
    videos = (data.get("videos") or [])[:5]
    apps = [a for a in (data.get("apps") or []) if a.get("rank")][:6]
    ranks = ((data.get("ranks") or {}).get("all") or [])[:8]

    news_lines = "\n".join(f"- [{clean(n.get('section'))}] {clean(n.get('title'))} ({clean(n.get('source'))})"
                           for n in news)
    post_lines = "\n".join(
        f"- ({clean(p.get('cat'))}) {clean(p.get('title'))} [{clean(p.get('source'))}] id={p.get('id')}"
        for p in posts)
    video_lines = "\n".join(
        f"- {clean(v.get('title'))} ({clean(v.get('channel'))}, 조회 {v.get('views', 0):,})" for v in videos)
    app_lines = "\n".join(f"- {a.get('platform')} {a.get('rank')}위 {clean(a.get('name'))} ({clean(a.get('category'))})"
                          for a in apps)
    kw = ", ".join(clean(r.get("k")) for r in ranks)
    total = count_items(data)

    return f"""너는 '트렌드픽(TrendPick)'의 편집장이다. 이 화면은 방문자가 오늘 무엇이 화제인지 3분 안에
파악하도록 돕는 트렌드 큐레이션 페이지다. 아래 수집 목록만 근거로 '오늘의 트렌드픽 브리프'를 쓴다.

[절대 규칙]
- 목록에 없는 사실·수치·기업명·전망을 만들지 않는다. 고유명사와 숫자는 목록에 있는 그대로만 쓴다.
- 제목을 그대로 베끼지 말고, 무엇이 함께 움직였는지·왜 오늘 눈에 띄는지를 편집자 관점에서 설명한다.
  단, 근거 없는 인과관계나 추측성 전망은 쓰지 않는다.
- 문체는 합니다체, 담백한 신문 해설체. 감탄·광고·홍보 표현과 이모지(emoji 필드 제외)는 쓰지 않는다.
- 같은 문장을 두 번 쓰지 않는다. 분야 이름만 나열하는 문단은 쓰지 않는다.

[문단 구성 — paragraphs 는 정확히 3개]
1문단: 오늘의 핵심 흐름. 가장 큰 이슈 2~3개를 골라 무엇이 어떻게 움직였는지 (280~360자)
2문단: 이슈별 포인트. 경제·증시 / IT·AI / 부동산·정책 / 사회·생활 중 목록에 있는 분야를 각각 한 문장씩,
       각 분야에서 무엇을 먼저 봐야 하는지 (280~380자)
3문단: 오늘 챙겨볼 것. 급상승 키워드, 영상·앱 순위, 마감 임박 공모전 등 실용 포인트 (200~300자)

[title] 오늘을 한 줄로 정의하는 편집 헤드라인. 22~38자. 따옴표·말줄임표 없이.
[lead] 화면 상단에 들어갈 1~2문장 요약. 110~180자.
[highlights] 핵심 포인트 3개. label 은 분야 이름, text 는 그 분야에서 오늘 꼭 알아야 할 한 문장(35~60자),
             source 는 근거 매체. 서로 다른 분야로 고른다.
[sections] 4~6개. label 분야, title 60자 이내 한 문장, body 2~3문장(150~260자),
           points 3개(각 40자 이내, '무엇을 확인하면 되는지' 실행형 문장) + title 에 근거 기사 제목을 그대로 복사.
[post_summaries] 아래 인기글 중 10개에 대해 {{"<id>": "한 줄 요약(35자 이내)"}}.

반드시 아래 JSON 스키마로만 응답하라(설명·마크다운 없이):
{{"title":"","lead":"","paragraphs":["","",""],
 "highlights":[{{"label":"","text":"","source":""}}],
 "sections":[{{"key":"econ|ai|estate|social|mom|apptech|build|comm","label":"","emoji":"","title":"","body":"","points":[{{"text":"","source":"","title":""}}]}}],
 "post_summaries":{{}}}}

[오늘] {data.get('issue', {}).get('date', '')} · 수집 {total}건 · 출처 {(data.get('stats') or {}).get('live_sources', '')}곳
[급상승 키워드] {kw}

[뉴스]
{news_lines}

[커뮤니티·특화 인기글]
{post_lines}

[유튜브 인기]
{video_lines}

[앱·게임 순위]
{app_lines}
"""


def call_gemini(prompt: str, key: str, model: str) -> dict:
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.45, "maxOutputTokens": 8192,
                             "responseMimeType": "application/json",
                             # gemini-2.5-flash 는 thinking 이 기본 켜짐 → 생각 토큰이 출력 한도를
                             # 잡아먹어 JSON 이 중간에 잘립니다. 브리프 작성에는 사고가 필요 없으므로 끕니다.
                             "thinkingConfig": {"thinkingBudget": 0}},
    }).encode("utf-8")
    req = urllib.request.Request(API.format(model=model, key=urllib.parse.quote(key)), data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = json.loads(resp.read())
    text = raw["candidates"][0]["content"]["parts"][0]["text"]
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


# ------------------------------------------------- 수집 항목과 링크 연결
def link_index(data: dict) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for k in ("news", "posts", "videos", "blogs"):
        for it in data.get(k) or []:
            t = it.get("title") or ""
            if t:
                idx.setdefault(key_of(t), it)
    return idx


def attach_links(result: dict, data: dict) -> None:
    """모델이 쓴 근거 제목을 실제 수집 항목과 맞춰 url·source 를 채웁니다(없으면 비워 둠)."""
    idx = link_index(data)
    for s in result.get("sections") or []:
        for p in s.get("points") or []:
            if not isinstance(p, dict):
                continue
            t = p.get("title") or p.get("text") or ""
            hit = idx.get(key_of(t))
            if hit is None:                      # 부분 일치로 한 번 더
                for kk, it in idx.items():
                    if kk and (kk in key_of(t) or key_of(t) in kk):
                        hit = it
                        break
            if hit:
                p["url"] = hit.get("url", "")
                p["source"] = p.get("source") or clean(hit.get("source") or hit.get("channel"))
                by_title = hit.get("title", "")
                p["title"] = by_title
            p.setdefault("url", "")
    # 하이라이트는 근거 기사 링크를 분야별 첫 포인트에서 가져옵니다
    by_label = {s.get("label"): s for s in result.get("sections") or []}
    for h in result.get("highlights") or []:
        if not isinstance(h, dict):
            continue
        sec = by_label.get(h.get("label"))
        if sec and not h.get("url"):
            pt = (sec.get("points") or [{}])[0]
            h["url"] = pt.get("url", "") if isinstance(pt, dict) else ""
            h["source"] = h.get("source") or (pt.get("source", "") if isinstance(pt, dict) else "")


def normalize_gemini(result: dict, base: dict) -> dict:
    """Gemini 응답을 방어적으로 정리합니다(빈 값은 규칙 기반 결과로 채움)."""
    out = dict(base)
    title = clean(result.get("title"))
    if title:
        out["title"] = short(title, 60)
    lead = clean(result.get("lead"))
    if lead:
        out["lead"] = lead

    paras = [clean(p) for p in (result.get("paragraphs") or []) if clean(p)]
    if len(paras) >= 2:                      # 2문단 이상일 때만 AI 문단 채택
        out["paragraphs"] = paras[:4]
        if not lead:
            out["lead"] = short(paras[0], 220)
    else:
        log("  AI 문단이 2개 미만 → 규칙 기반 문단 유지")

    secs = result.get("sections") or []
    good = []
    for s in secs:
        if not isinstance(s, dict) or not clean(s.get("title")):
            continue
        body = clean(s.get("body"))
        pts = []
        for p in s.get("points") or []:
            if isinstance(p, str) and clean(p):
                pts.append({"text": clean(p), "source": "", "url": "", "title": ""})
            elif isinstance(p, dict) and clean(p.get("text")):
                pts.append({"text": clean(p["text"]), "source": clean(p.get("source")),
                            "url": "", "title": clean(p.get("title"))})
        if not body or len(pts) < 2:
            continue
        key = clean(s.get("key")) or "news"
        good.append({"key": key, "label": clean(s.get("label")) or "분야",
                     "emoji": clean(s.get("emoji")) or "📰",
                     "title": short(clean(s["title"]), 80), "body": body, "points": pts[:3]})
    if len(good) >= 3:
        out["sections"] = good[:6]
    else:
        log("  AI 섹션이 3개 미만 → 규칙 기반 섹션 유지")

    hl = []
    for h in result.get("highlights") or []:
        if isinstance(h, dict) and clean(h.get("text")):
            hl.append({"label": clean(h.get("label")), "text": clean(h["text"]),
                       "source": clean(h.get("source")), "url": ""})
    if len(hl) >= 2:
        out["highlights"] = hl[:3]
    out["post_summaries"] = result.get("post_summaries") or {}
    return out


# --------------------------------------------------------------- 메인
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 규칙 요약만")
    args = ap.parse_args()

    path = Path(args.data)
    if not path.exists():
        log(f"data.json 이 없습니다: {path} · collector.py 를 먼저 실행하세요")
        return 0

    data = json.loads(path.read_text(encoding="utf-8"))
    key = os.environ.get("GEMINI_API_KEY", "").strip()

    # 1) 규칙 기반 브리프는 항상 만듭니다(키가 없거나 API 가 실패해도 이 결과로 화면이 채워집니다).
    base = rule_brief(data)
    brief = data.get("brief") or {}
    base.update({
        "no": brief.get("no") or f"No.{data.get('issue', {}).get('no', 1):02d}",
        "date": brief.get("date") or data.get("issue", {}).get("date") or datetime.now(KST).strftime("%Y-%m-%d"),
        "label": brief.get("label") or datetime.now(KST).strftime("%m.%d"),
        "weekday": brief.get("weekday") or "월화수목금토일"[datetime.now(KST).weekday()],
        "picks": brief.get("picks") or [],
        "metrics": brief.get("metrics") or {},
        "past": brief.get("past") or [],
    })

    # 2) 키가 있으면 Gemini 로 문장을 다듬습니다.
    result = None
    if key and not args.dry_run:
        prompt = build_prompt(data)
        RETRY_STATUS = (429, 500, 502, 503, 504)
        for model in [MODEL] + FALLBACK_MODELS:
            for attempt in range(1, 4):
                try:
                    suffix = f" (재시도 {attempt - 1})" if attempt > 1 else ""
                    log(f"Gemini 브리프 요청 · model={model}{suffix}")
                    result = call_gemini(prompt, key, model)
                    result["engine"] = f"gemini:{model}"
                    break
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", "replace")[:200]
                    log(f"  실패 HTTP {exc.code} · {detail}")
                    if exc.code in RETRY_STATUS and attempt < 3:
                        time.sleep(5 * attempt)
                        continue
                    break
                except Exception as exc:  # noqa: BLE001
                    log(f"  실패 {type(exc).__name__}: {exc}")
                    break
            if result:
                break
        if result is None:
            log("Gemini 호출 실패 → 규칙 기반 브리프로 대체")
    elif not key:
        log("GEMINI_API_KEY 미설정 → 규칙 기반 브리프로 대체 (2~3문단 해설까지 생성)")

    if result:
        base = normalize_gemini(result, base)
        attach_links(base, data)
        base["engine"] = result.get("engine", "gemini")

    # 3) 최소 분량 보증 — AI 결과가 짧아도 브리프 전문이 비지 않도록
    if len(base.get("paragraphs") or []) < 2:
        base["paragraphs"] = rule_paragraphs(data, base.get("sections") or [])
    if not base.get("highlights"):
        base["highlights"] = rule_highlights(base.get("sections") or [])
    if not base.get("lead"):
        base["lead"] = rule_lead(data, base.get("sections") or [], base.get("paragraphs") or [])

    data["brief"] = base

    # 4) 인기글 한 줄 요약 반영
    summaries = base.get("post_summaries") or {}
    for p in data.get("posts", []):
        if p.get("id") in summaries:
            p["summary"] = clean(summaries[p["id"]])

    data["summary_meta"] = {
        "engine": base.get("engine"),
        "model": MODEL if key else "",
        "at": datetime.now(KST).isoformat(timespec="seconds"),
        "paragraphs": len(base.get("paragraphs") or []),
        "sections": len(base.get("sections") or []),
        "post_summaries": len(summaries),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"브리프 반영 · engine={base.get('engine')} · 문단 {len(base.get('paragraphs') or [])}개 · "
        f"분야 {len(base.get('sections') or [])}개 · {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
