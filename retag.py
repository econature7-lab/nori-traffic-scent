#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
트렌드픽 TrendPick v3 · retag.py
================================
분류 규칙(collector.py)을 고친 뒤, **이미 수집된 data.json**에 같은 규칙을 다시 적용합니다.
(제목·링크·수치 같은 사실 데이터는 건드리지 않고 section/topics 태그만 다시 계산)

  1) 뉴스 section · topics 재계산  (예전에는 피드 분야를 그대로 주제로 옮겨 오분류)
  2) 커뮤니티·뉴스의 자극적·선정적 제목 제거 (애드핏 심사 감점 위험)
  3) 테스트성 공모전(name='test' 등) 제거
  4) 부동산·경매 주제 글이 0건이면 공개 RSS(한국경제 부동산 등)에서 실제 기사로 보충
  5) 블로그 글 중 썸네일이 없는 항목은 원문 og:image 로 보강
  6) 인기 웹툰(네이버웹툰 공개 목록)을 새로 수집해 웹툰 주제로 태깅
     → 지어낸 기사·작품은 넣지 않습니다.

사용법
  python retag.py                 # data.json 제자리 정리
  python retag.py --no-topup      # 보충 수집 없이 태그만 다시 계산
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data.json"


def load_collector():
    spec = importlib.util.spec_from_file_location("collector", ROOT / "collector.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description="data.json 재분류")
    ap.add_argument("--path", default=str(DATA))
    ap.add_argument("--no-topup", action="store_true", help="부동산 기사 보충 수집 생략")
    ap.add_argument("--min-estate", type=int, default=5, help="부동산·경매 최소 기사 수")
    args = ap.parse_args()

    col = load_collector()
    path = Path(args.path)
    data = json.loads(path.read_text(encoding="utf-8"))
    feed_default = {name: default for _, name, _, default in col.NEWS_FEEDS}

    # 1) 뉴스 재분류 -------------------------------------------------------
    kept_news, dropped_news = [], []
    for n in data.get("news", []):
        if col.is_sensitive(n.get("title", ""), n.get("desc", "") or n.get("summary", "")):
            dropped_news.append(n.get("title", ""))
            continue
        default = feed_default.get(n.get("source", ""), n.get("section") or "사회·생활")
        n["section"] = col.section_rules(n.get("title", ""), default)
        n["topics_kw"] = col.topic_tags(n.get("title", ""))
        n["topics"] = col.topic_tags(f"{n.get('title', '')} {n.get('source', '')}")
        kept_news.append(n)
    data["news"] = kept_news

    # 2) 커뮤니티·블로그·영상 정리 -----------------------------------------
    kept_posts, dropped_posts = [], []
    for p in data.get("posts", []):
        if col.is_sensitive(p.get("title", ""), p.get("desc", "") or p.get("summary", "")):
            dropped_posts.append(p.get("title", ""))
            continue
        p["topics_kw"] = col.topic_tags(p.get("title", ""))
        p["topics"] = col.topic_tags(f"{p.get('title', '')} {p.get('source', '')}")
        kept_posts.append(p)
    data["posts"] = kept_posts

    for key in ("videos", "blogs"):
        for it in data.get(key, []):
            text = f"{it.get('title', '')} {it.get('channel', '') or it.get('source', '')}"
            it["topics_kw"] = col.topic_tags(it.get("title", ""))
            it["topics"] = col.topic_tags(text)

    # 2-b) 블로그 썸네일 보강 (이미지가 없는 글만 · 원문 og:image)
    missing_blog = [b for b in data.get("blogs", []) if not b.get("img")]
    if missing_blog:
        filled = col.enrich_images(missing_blog, budget_sec=25.0, workers=6, limit=12)
        print("블로그 썸네일 보강", filled, "/", len(missing_blog))

    # 2-c) 인기 웹툰 (네이버웹툰 요일 연재 · 평점 순)
    if not args.no_topup:
        webtoons = col.collect_webtoons()
        if webtoons:
            data["webtoons"] = webtoons
            print("웹툰·엔터 수집", len(webtoons), "건")
        else:
            print("웹툰 수집 실패 → 기존 웹툰 데이터 유지", len(data.get("webtoons") or []), "건")
    for w in data.get("webtoons", []):
        w["topics"] = ["webtoon"]
        w["topics_kw"] = ["webtoon"]

    # 3) 테스트성 공모전 제거 ---------------------------------------------
    before_h = len(data.get("hackathons", []))
    data["hackathons"] = [h for h in data.get("hackathons", [])
                          if not col.is_bogus_hackathon(h.get("name", ""))]
    dropped_h = before_h - len(data["hackathons"])

    # 4) 부동산·경매 기사 보충 (실제 RSS 기사만) ----------------------------
    added = []
    estate = [n for n in data["news"] if "estate" in (n.get("topics") or [])]
    if not args.no_topup and len(estate) < args.min_estate:
        print("부동산·경매 글이 부족 → 공개 RSS에서 실제 기사를 보충합니다")
        fresh = col.collect_news()
        seen_titles = {re.sub(r"\W+", "", n.get("title", "")) for n in data["news"]}
        seen_urls = {n.get("url", "") for n in data["news"]}
        pool = [n for n in fresh
                if "estate" in col.topic_tags(f"{n.get('title', '')} {n.get('source', '')}")
                and re.sub(r"\W+", "", n.get("title", "")) not in seen_titles
                and n.get("url") not in seen_urls]
        added_items = []
        for i, n in enumerate(pool[: max(0, args.min_estate * 2)]):
            n = dict(n)
            n["cat"] = "news"
            n["hot"] = max(40, 86 - i)
            n["rise"] = max(90, 250 - i * 6)
            n["comments"] = 0
            n["views"] = 0
            n["sample"] = False
            n["topics_kw"] = col.topic_tags(n.get("title", ""))
            n["topics"] = col.topic_tags(f"{n.get('title', '')} {n.get('source', '')}")
            if "estate" not in n["topics"]:
                continue
            data["news"].append(n)
            added_items.append(n)
            added.append(n.get("title", ""))
        if added_items:
            col.enrich_images([n for n in added_items if not n.get("img")],
                              budget_sec=20.0, workers=6, limit=12)

    # 5) 수치·메타 정리 -----------------------------------------------------
    if isinstance(data.get("stats"), dict):
        data["stats"]["news"] = len(data["news"])
        data["stats"]["collected"] = (len(data["news"]) + len(data.get("posts", []))
                                      + len(data.get("videos", [])) + len(data.get("blogs", []))
                                      + len(data.get("webtoons", [])))
    # 6) 브리프 수치·키워드 표기 정리 ---------------------------------------
    brief = data.get("brief") or {}
    metrics = brief.get("metrics")
    if isinstance(metrics, dict):
        metrics["news"] = len(data["news"])
        metrics["items"] = sum(len(data.get(k, [])) for k in
                               ("posts", "news", "videos", "blogs", "webtoons", "deals",
                                "opensource", "apps", "hackathons"))
        metrics["topics"] = len(brief.get("sections") or []) or metrics.get("topics")
    # 구글 트렌드 키워드에 섞인 자동 띄어쓰기('12 월 3 일')를 바로잡습니다
    ranks = data.get("ranks") or {}
    for row in ranks.get("all") or []:
        row["k"] = re.sub(r"(\d)\s+(월|일|년|주|개|건|명|분|초)", r"\1\2", str(row.get("k", "")))

    # 7) 썸네일 집계 재계산 ------------------------------------------------
    data["thumbs"] = col.thumb_stats(data)

    data["retag"] = {
        "at": datetime.now(col.KST).isoformat(timespec="seconds"),
        "rule": "keyword-score-v2",
        "news_dropped_sensitive": len(dropped_news),
        "posts_dropped_sensitive": len(dropped_posts),
        "hackathons_dropped": dropped_h,
        "estate_added": len(added),
    }

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"정리 완료 · {path}")
    print("  뉴스 유지", len(data["news"]), "· 민감 제외", len(dropped_news))
    print("  커뮤니티 유지", len(data["posts"]), "· 민감 제외", len(dropped_posts))
    print("  공모전", len(data["hackathons"]), "· 테스트 제외", dropped_h)
    print("  부동산 보충", len(added), "· 웹툰", len(data.get("webtoons") or []))
    for t in dropped_news:
        print("   - news 제외:", t[:70])
    for t in dropped_posts:
        print("   - post 제외:", t[:70])
    for t in added:
        print("   + estate:", t[:70])
    return 0


if __name__ == "__main__":
    sys.exit(main())
