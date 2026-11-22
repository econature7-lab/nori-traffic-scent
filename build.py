#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
트렌드픽(TrendPick) v3 · build.py
==================================
src/shell.html + src/app.css + src/app.js + data.json 을 하나의 오프라인 HTML로 합치고,
애드센스 심사용 고정 페이지 4종 · robots.txt · sitemap.xml · data/creators.json 을 함께 만듭니다.

  python build.py
    → work/nori-traffic-scent/index.html          (GitHub Pages 배포용)
    → downloads/트렌드픽_v3.html                   (단독 실행본 · 사용자에게 보여줄 파일)
    → about.html / policy.html / privacy.html / contact.html
    → robots.txt / sitemap.xml
    → data/creators.json                           (지연_X · 블로그 자동화가 읽는 경량 JSON)

외부 CDN·웹폰트 의존 0건 / 내장 데이터로 file:// 에서도 즉시 동작.
(광고 ID를 넣은 경우에만 애드센스·애드핏 스크립트를 그때 불러옵니다.)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WS = ROOT.parents[1]              # /workspace
SRC = ROOT / "src"
PAGES_DIR = SRC / "pages"
OUT_LOCAL = ROOT / "index.html"
OUT_DOWNLOAD = WS / "downloads" / "트렌드픽_v3.html"
SITE = "https://econature7-lab/nori-traffic-scent/"
REPO = "econature7-lab/nori-traffic-scent"
KST = timezone(timedelta(hours=9))

KEEP_KEYS = [
    "schema", "generated_at", "issue", "stats", "sources", "youtube_mode", "site",
    "posts", "news", "videos", "blogs", "deals", "opensource", "apps", "hackathons",
    "ranks", "brief", "thumbs", "collect_log", "notes",
]

AD_HOSTS = ("pagead2.googlesyndication.com", "t1.daumcdn.net")

# ── 고정 페이지 (about · policy · privacy · contact) ────────────────────────
PAGES = [
    ("about", "소개",
     "트렌드픽이 무엇을 왜 모으는지, 하루 두 번(07:17 · 19:17 KST) 자동 수집 구조와 다섯 분야를 소개합니다."),
    ("policy", "편집원칙",
     "공개 RSS·공식 API 실데이터 원칙, 원문 출처·저작권 존중, AI 요약 검수와 정정 기준을 안내합니다."),
    ("privacy", "개인정보처리방침",
     "트렌드픽의 개인정보 처리, 브라우저 저장소, 구글 애드센스·카카오 애드핏 광고 쿠키, 쿠팡 파트너스 고지를 안내합니다."),
    ("contact", "문의",
     "트렌드픽 운영팀 문의 창구, 기사 수정·삭제 요청 절차, 제휴·광고 문의를 안내합니다."),
]
NAV = [("index", "홈"), ("about", "소개"), ("policy", "편집원칙"),
       ("privacy", "개인정보"), ("contact", "문의")]

BRAND_SVG = (
    '<svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">'
    '<rect width="32" height="32" rx="9" fill="#111827"/>'
    '<path d="M8.5 22.5 14 15.4l4 3.4 5.2-8.3" fill="none" stroke="#E11D48" stroke-width="2.6" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="23.4" cy="10.4" r="2.6" fill="#0D9488"/></svg>'
)
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='8' fill='%23111827'/%3E"
    "%3Cpath d='M8.5 22.5 14 15.4l4 3.4 5.2-8.3' fill='none' stroke='%23E11D48' stroke-width='2.6' "
    "stroke-linecap='round' stroke-linejoin='round'/%3E"
    "%3Ccircle cx='23.4' cy='10.4' r='2.6' fill='%230D9488'/%3E%3C/svg%3E"
)

# ── creators.json 주제 ───────────────────────────────────────────────────
TOPIC_KEYS = [
    ("ai", "AI·부업"),
    ("estate", "부동산·경매"),
    ("mom", "맘카페·육아"),
    ("apptech", "앱테크·핫딜"),
    ("build", "건축·입찰"),
]


def now_kst() -> datetime:
    return datetime.now(KST)


def page_shell(slug: str, label: str, desc: str, body: str, css: str) -> str:
    nav = "".join(
        '<a href="{href}"{on}>{txt}</a>'.format(
            href="index.html" if key == "index" else f"{key}.html",
            on=' class="on" aria-current="page"' if key == slug else "",
            txt=txt,
        )
        for key, txt in NAV
    )
    url = SITE + f"{slug}.html"
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#F7F6F2">
<title>{label} · 트렌드픽 TrendPick</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="트렌드픽 TrendPick">
<meta property="og:title" content="{label} · 트렌드픽">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}og.png">
<meta property="og:locale" content="ko_KR">
<link rel="icon" href="{FAVICON}">
<link rel="sitemap" type="application/xml" title="sitemap" href="{SITE}sitemap.xml">
<style>
{css}
</style>
</head>
<body>
<header class="pmast">
  <div class="pmast-in">
    <a class="pbrand" href="index.html" aria-label="트렌드픽 홈">
      {BRAND_SVG}
      <span class="pbrand-txt"><b>트렌드픽</b><i>TRENDPICK</i></span>
    </a>
    <nav class="pnav" aria-label="페이지">{nav}</nav>
  </div>
</header>
{body}
<footer class="pfoot">
  <div class="pfoot-in">
    <div class="pfoot-brand">{BRAND_SVG}<b>트렌드픽 TrendPick</b></div>
    <p>공개 RSS · 공식 API 로 수집한 실제 데이터만 보여 줍니다. 기사 저작권은 각 매체에 있으며, 모든 카드는 원문으로 연결됩니다.<br>
    트렌드픽은 쿠팡 파트너스 활동의 일환으로 일정액의 수수료를 제공받습니다.</p>
    <div class="pfoot-links">
      <a href="index.html">메인</a>
      <a href="about.html">소개</a>
      <a href="policy.html">편집원칙</a>
      <a href="privacy.html">개인정보처리방침</a>
      <a href="contact.html">문의</a>
      <a href="https://github.com/{REPO}" target="_blank" rel="noopener">GitHub</a>
      <span class="micro">© 2026 TrendPick</span>
    </div>
  </div>
</footer>
</body>
</html>
"""


def write_pages(css: str) -> list[Path]:
    written = []
    for slug, label, desc in PAGES:
        src = PAGES_DIR / f"{slug}.html"
        if not src.exists():
            print(f"페이지 원본 없음 · {src}")
            continue
        html = page_shell(slug, label, desc, src.read_text(encoding="utf-8").strip(), css)
        out = ROOT / f"{slug}.html"
        out.write_text(html, encoding="utf-8")
        written.append(out)
    return written


def write_seo_files(today: str) -> list[Path]:
    robots = (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {SITE}sitemap.xml\n"
    )
    (ROOT / "robots.txt").write_text(robots, encoding="utf-8")

    urls = [
        (SITE, today, "daily", "1.0"),
        (SITE + "about.html", today, "monthly", "0.7"),
        (SITE + "policy.html", today, "monthly", "0.6"),
        (SITE + "privacy.html", today, "monthly", "0.6"),
        (SITE + "contact.html", today, "monthly", "0.6"),
    ]
    body = "".join(
        "  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"    <changefreq>{freq}</changefreq>\n"
        f"    <priority>{prio}</priority>\n"
        "  </url>\n"
        for loc, lastmod, freq, prio in urls
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + body +
        "</urlset>\n"
    )
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    return [ROOT / "robots.txt", ROOT / "sitemap.xml"]


def build_creators(payload: dict) -> dict:
    """지연_X · 네이버 블로그 자동화가 가볍게 긁어갈 정적 JSON."""
    items: list[dict] = []
    for key, kind in (("posts", "post"), ("news", "news"), ("videos", "video"), ("blogs", "blog")):
        for it in payload.get(key) or []:
            if not it.get("title"):
                continue
            tags = sorted(set(it.get("topics") or []) | set(it.get("topics_kw") or []))
            items.append({
                "title": it.get("title", ""),
                "source": it.get("source") or it.get("channel", ""),
                "url": it.get("url", ""),
                "kind": kind,
                "time": it.get("time", ""),
                "published": it.get("published", ""),
                "hot": it.get("hot", 0),
                "topics": tags,
            })

    seen: set[str] = set()
    unique: list[dict] = []
    for it in items:
        key = re.sub(r"\s+", "", (it["title"] or "")[:50])
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(it)

    topics = {}
    for key, label in TOPIC_KEYS:
        rows = [x for x in unique if key in x["topics"] and x.get("url")]
        rows.sort(key=lambda x: -(x.get("hot") or 0))
        topics[key] = {
            "label": label,
            "count": len(rows),
            "items": [
                {k: r[k] for k in ("title", "source", "url", "kind", "time", "hot")}
                for r in rows[:5]
            ],
        }

    brief = payload.get("brief") or {}
    ranks = (payload.get("ranks") or {}).get("all") or []
    return {
        "schema": "trendpick/creators/1",
        "generated_at": payload.get("generated_at"),
        "site": payload.get("site") or {"repo": REPO, "pages_url": SITE},
        "issue": payload.get("issue"),
        "schedule": {"timezone": "Asia/Seoul", "runs": ["07:17", "19:17"]},
        "top10": [
            {"rank": i + 1, "keyword": r.get("k", ""), "rise": r.get("r"),
             "source": r.get("src", ""), "url": r.get("url", "")}
            for i, r in enumerate(ranks[:10])
        ],
        "brief": {
            "no": brief.get("no"), "date": brief.get("date"), "label": brief.get("label"),
            "title": brief.get("title"), "lead": brief.get("lead"), "engine": brief.get("engine"),
            "picks": [
                {k: p.get(k) for k in ("rank", "label", "title", "source", "url")}
                for p in (brief.get("picks") or [])
            ],
            "sections": [
                {
                    "key": s.get("key"), "label": s.get("label"), "title": s.get("title"),
                    "body": s.get("body"),
                    "points": [
                        {"text": (p if isinstance(p, str) else p.get("text")),
                         "source": ("" if isinstance(p, str) else p.get("source", "")),
                         "url": ("" if isinstance(p, str) else p.get("url", ""))}
                        for p in (s.get("points") or [])
                    ],
                }
                for s in (brief.get("sections") or [])
            ],
        },
        "topics": topics,
        "note": "트렌드픽이 하루 두 번 만드는 경량 피드입니다. 출처 URL을 함께 보관하고, 원문 확인 후 인용하세요.",
    }


def main() -> int:
    shell = (SRC / "shell.html").read_text(encoding="utf-8")
    css = (SRC / "app.css").read_text(encoding="utf-8")
    js = (SRC / "app.js").read_text(encoding="utf-8")

    data_path = ROOT / "data.json"
    payload: dict = {}
    if data_path.exists():
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        embedded = {k: payload.get(k) for k in KEEP_KEYS if k in payload}
    else:
        embedded = {"posts": [], "news": [], "notes": ["data.json 이 없습니다. collector.py 를 먼저 실행하세요."]}

    data_json = json.dumps(embedded, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</", "<\\/")   # </script> 조기 종료 방지

    html = (shell.replace("{{CSS}}", css)
                 .replace("{{JS}}", js)
                 .replace("{{DATA_JSON}}", data_json))

    targets = [OUT_LOCAL]
    if WS.exists() and (WS / "downloads").exists():
        targets.append(OUT_DOWNLOAD)      # 로컬 작업공간에서만 단독 실행본도 함께 저장
    for out in targets:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"빌드 완료 · {out} ({out.stat().st_size:,} bytes)")

    # 고정 페이지 4종 (about · policy · privacy · contact)
    pages_css = (SRC / "pages.css").read_text(encoding="utf-8")
    for out in write_pages(pages_css):
        print(f"페이지 생성 · {out.name} ({out.stat().st_size:,} bytes)")

    # robots.txt · sitemap.xml
    today = now_kst().strftime("%Y-%m-%d")
    for out in write_seo_files(today):
        print(f"SEO 파일 · {out.name}")

    # data/creators.json — X·블로그 자동화용 경량 피드
    if payload:
        creators = build_creators(payload)
        cpath = ROOT / "data" / "creators.json"
        cpath.parent.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps(creators, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        filled = sum(1 for k in topics_counts(creators) if creators["topics"][k]["items"])
        print(f"경량 피드 · {cpath} · top10 {len(creators['top10'])}건 · "
              f"분야 {filled}/5 · 항목 {sum(len(creators['topics'][k]['items']) for k in topics_counts(creators))}건")

    # 외부 의존 점검 (광고 스크립트는 ID를 넣었을 때만 로드되는 선택 사항)
    check_html = html + "".join((ROOT / f"{s}.html").read_text(encoding="utf-8") for s, _, _ in PAGES
                                  if (ROOT / f"{s}.html").exists())
    external_patterns = [
        r'<script[^>]+src=["\'](https?://[^"\']+)',
        r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\'](https?://[^"\']+)',
        r'@import\s+url\(["\']?(https?://[^)"\']+)',
        r'<img[^>]+src=["\'](https?://[^"\']+)',
    ]
    found = []
    for pat in external_patterns:
        found.extend(re.findall(pat, check_html, re.I))
    found = [u for u in found if not any(h in u for h in AD_HOSTS)]
    print("외부 리소스 참조:", "없음" if not found else sorted(set(found))[:5])

    # 남은 서비스명 점검
    legacy = len(re.findall(r"트래픽센트|Traffic Scent|trafficscent", check_html, re.I))
    print("구 서비스명 잔존:", legacy, "건")
    print("내장 데이터:", len(embedded.get("posts", [])), "posts ·",
          len(embedded.get("news", [])), "news ·",
          len(embedded.get("videos", [])), "videos ·",
          len(embedded.get("blogs", [])), "blogs")
    return 0


def topics_counts(creators: dict) -> list[str]:
    return [k for k, _ in TOPIC_KEYS]


if __name__ == "__main__":
    sys.exit(main())
