#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
트렌드픽 TrendPick v3 · summarize.py
===================================
collector.py 가 만든 data.json 을 읽어
  1) DAILY BRIEF(일간 트렌드 리포트) 요약
  2) 상위 인기글 한 줄 요약
을 채워 넣습니다.

- GEMINI_API_KEY 가 있으면 Gemini Flash 무료 티어 REST API 호출 (PC 클로드 한도 미사용)
- 키가 없거나 호출이 실패하면 **규칙 기반 요약으로 대체**하고도 data.json 은 정상 생성
- 어떤 경우에도 스크립트가 0이 아닌 코드로 끝나 GitHub Actions 를 깨뜨리지 않습니다.

사용법
  python summarize.py                 # data.json 제자리 갱신
  python summarize.py --dry-run       # API 호출 없이 규칙 요약만
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
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


def log(msg: str) -> None:
    print(f"[{datetime.now(KST):%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------- 규칙 기반
def rule_summary(data: dict) -> dict:
    """키 없이도 쓸 수 있는 요약. 뉴스 섹션별 헤드라인 + 커뮤니티 상위 제목을 묶습니다."""
    news = data.get("news", [])
    posts = data.get("posts", [])
    by_section: dict[str, list[dict]] = {}
    for n in news:
        by_section.setdefault(n.get("section", "뉴스"), []).append(n)

    label_map = {"경제·증시": ("econ", "📈"), "IT·AI": ("ai", "🤖"),
                 "부동산·정책": ("estate", "🏢"), "사회·생활": ("social", "🧾")}
    sections = []
    for section, items in by_section.items():
        if not items:
            continue
        key, emoji = label_map.get(section, ("news", "📰"))
        titles = [i["title"] for i in items[:3]]
        sections.append({
            "key": key, "label": section, "emoji": emoji,
            "title": titles[0][:90],
            "body": " / ".join(titles)[:300],
            "points": [f"{i['source']} · {i['title'][:60]}" for i in items[:3]],
        })

    # 특화 분야 상위 글 한 줄
    for cat, label, emoji in [("mom", "맘카페·육아", "🌿"), ("estate", "부동산·경매", "🏢"),
                              ("ai", "AI·부업", "🤖"), ("apptech", "앱테크", "💰"),
                              ("build", "건축·입찰", "📐")]:
        rows = [p for p in posts if p.get("cat") == cat][:3]
        if not rows:
            continue
        sections.append({
            "key": cat, "label": label, "emoji": emoji,
            "title": rows[0]["title"][:90],
            "body": " / ".join(p["title"] for p in rows)[:260],
            "points": [f"{p['source']} · {p['title'][:56]}" for p in rows],
        })

    if not sections:
        sections = [{"key": "comm", "label": "커뮤니티", "emoji": "💬",
                     "title": "오늘 수집된 인기글", "body": "수집 결과가 적은 날입니다.",
                     "points": [p["title"][:50] for p in posts[:3]]}]

    lead_bits = [s["title"] for s in sections[:3]]
    return {
        "title": " · ".join(t[:40] for t in lead_bits),
        "lead": ("오늘 수집한 기사와 인기글을 분야별로 정리했습니다. " +
                 " / ".join(lead_bits[:4]))[:600],
        "sections": sections[:6],
        "post_summaries": {},
        "engine": "rule-based",
    }


# ---------------------------------------------------------------- Gemini
def build_prompt(data: dict) -> str:
    news = data.get("news", [])[:24]
    posts = data.get("posts", [])[:18]
    ranks = data.get("ranks", {}).get("all", [])[:7]

    news_lines = "\n".join(f"- [{n['section']}] {n['title']} ({n['source']})" for n in news)
    post_lines = "\n".join(f"- ({p['cat']}) {p['title']} [{p['source']}]  id={p['id']}" for p in posts[:10]) + \
        "\n" + "\n".join(f"- ({p['cat']}) {p['title']} [{p['source']}]" for p in posts[10:])
    kw = ", ".join(r["k"] for r in ranks)

    return f"""너는 '트렌드픽(TrendPick)'의 편집자다. 이 화면은 방문자가 오늘 무엇이 화제인지 3분 안에
파악하도록 돕는 트렌드 큐레이션 페이지다.

아래 수집 목록을 근거로 '오늘의 트렌드픽 브리프'를 한국어로 작성하라.
- 확인된 내용만 쓴다. 목록에 없는 사실·수치를 만들지 않는다.
- 섹션은 4~6개: 경제·증시 / IT·AI / 부동산·정책 / 사회·생활 중 목록에 있는 것 + 특화 분야(맘카페·AI부업 등).
- 각 섹션: title(한 문장, 60자 이내), body(2~3문장, 어떤 흐름인지), points(3개, 각 40자 이내 실행 포인트).
- lead: 3~4문장 종합.
- post_summaries: 아래 인기글 중 10개에 대해 {{"<id>": "한 줄 요약(35자 이내)"}} 형태. id 는 각 줄 끝 `id=c_...` 값을 그대로 쓴다.

반드시 아래 JSON 스키마로만 응답하라(설명·마크다운 없이):
{{"title":"","lead":"","sections":[{{"key":"econ|ai|estate|social|mom|apptech|build|comm","label":"","emoji":"","title":"","body":"","points":["","",""]}}],"post_summaries":{{}}}}

[오늘] {data.get('issue', {}).get('date', '')}
[급상승 키워드] {kw}

[뉴스]
{news_lines}

[커뮤니티·특화 인기글]
{post_lines}
"""


def call_gemini(prompt: str, key: str, model: str) -> dict:
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192,
                             "responseMimeType": "application/json",
                             # gemini-2.5-flash 는 thinking 이 기본 켜짐 → 생각 토큰이 출력 한도를
                             # 잡아먹어 JSON 이 중간에 잘립니다. 브리프 요약에는 사고가 필요 없으므로 끕니다.
                             "thinkingConfig": {"thinkingBudget": 0}},
    }).encode("utf-8")
    req = urllib.request.Request(API.format(model=model, key=urllib.parse.quote(key)), data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = json.loads(resp.read())
    text = raw["candidates"][0]["content"]["parts"][0]["text"]
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


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
    result = None

    if key and not args.dry_run:
        prompt = build_prompt(data)
        for model in [MODEL] + FALLBACK_MODELS:
            try:
                log(f"Gemini 요약 요청 · model={model}")
                result = call_gemini(prompt, key, model)
                result["engine"] = f"gemini:{model}"
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:200]
                log(f"  실패 HTTP {exc.code} · {detail}")
            except Exception as exc:  # noqa: BLE001
                log(f"  실패 {type(exc).__name__}: {exc}")
        if result is None:
            log("Gemini 호출 실패 → 규칙 기반 요약으로 대체")
    elif not key:
        log("GEMINI_API_KEY 미설정 → 규칙 기반 요약으로 대체 (data.json 은 정상 생성)")

    # 키가 없을 때: collector.py 가 만든 브리프(분야 가중치·연예/스포츠 감점 반영)를 그대로 사용.
    # 브리프가 없는 예전 data.json 이면 규칙 기반 요약을 새로 만듭니다.
    existing = data.get("brief") or {}
    if existing.get("sections"):
        base = {
            "title": existing.get("title") or "오늘의 트렌드 리포트",
            "lead": existing.get("lead") or "",
            "sections": existing.get("sections"),
            "post_summaries": {},
            "engine": existing.get("engine") or "rule-based",
        }
    else:
        base = rule_summary(data)
    if result:
        base.update({
            "title": result.get("title") or base["title"],
            "lead": result.get("lead") or base["lead"],
            "sections": result.get("sections") or base["sections"],
            "post_summaries": result.get("post_summaries") or {},
            "engine": result.get("engine", "gemini"),
        })

    brief = data.get("brief") or {}
    brief.update({
        "no": brief.get("no") or f"No.{data.get('issue', {}).get('no', 1):02d}",
        "date": (data.get("issue", {}).get("date") or datetime.now(KST).strftime("%Y-%m-%d")),
        "label": brief.get("label") or datetime.now(KST).strftime("%m.%d"),
        "title": base["title"],
        "lead": base["lead"],
        "sections": base["sections"],
        "engine": base["engine"],
    })
    data["brief"] = brief

    # 인기글 한 줄 요약 반영
    summaries = base.get("post_summaries") or {}
    for p in data.get("posts", []):
        if p["id"] in summaries:
            p["summary"] = summaries[p["id"]]

    data["summary_meta"] = {
        "engine": base["engine"],
        "model": MODEL if key else "",
        "at": datetime.now(KST).isoformat(timespec="seconds"),
        "post_summaries": len(summaries),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"요약 반영 완료 · engine={base['engine']} · sections={len(brief['sections'])} · {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
