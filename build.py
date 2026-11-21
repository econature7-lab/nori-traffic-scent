#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
노리짱 트래픽센트 v2 · build.py
================================
src/shell.html + src/app.css + src/app.js + data.json 을 하나의 오프라인 HTML로 합칩니다.

  python build.py
    → work/nori-traffic-scent/index.html            (GitHub Pages 배포용)
    → downloads/노리짱_트래픽센트_v2.html            (사용자에게 보여줄 단일 파일)

외부 CDN·웹폰트·외부 이미지 0건 / 내장 데이터로 file:// 에서도 즉시 동작.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WS = ROOT.parents[1]              # /workspace
SRC = ROOT / "src"
OUT_LOCAL = ROOT / "index.html"
OUT_DOWNLOAD = WS / "downloads" / "노리짱_트래픽센트_v2.html"


def main() -> int:
    shell = (SRC / "shell.html").read_text(encoding="utf-8")
    css = (SRC / "app.css").read_text(encoding="utf-8")
    js = (SRC / "app.js").read_text(encoding="utf-8")

    data_path = ROOT / "data.json"
    if data_path.exists():
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        # 내장 데이터는 화면에서 쓰는 필드만 남겨 파일 크기를 줄입니다.
        embedded = {k: payload.get(k) for k in [
            "schema", "generated_at", "issue", "stats", "sources", "youtube_mode", "site",
            "posts", "news", "videos", "blogs", "deals", "opensource", "apps",
            "hackathons", "benchmarks", "indie", "ranks", "brief", "visits", "notes",
        ] if k in payload}
    else:
        embedded = {"posts": [], "news": [], "notes": ["data.json 이 없습니다. collector.py 를 먼저 실행하세요."]}

    data_json = json.dumps(embedded, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</", "<\\/")   # </script> 조기 종료 방지

    html = shell.replace("{{CSS}}", css).replace("{{JS}}", js).replace("{{DATA_JSON}}", data_json)

    for out in (OUT_LOCAL, OUT_DOWNLOAD):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"빌드 완료 · {out} ({out.stat().st_size:,} bytes)")

    # 외부 의존 점검
    leaks = []
    for token in ("http://", "https://"):
        for line in html.splitlines():
            low = line.strip().lower()
            if token in low and ("<link" in low or "<script" in low or "src=" in low or "url(" in low):
                leaks.append(line.strip()[:120])
    print("외부 리소스 참조:", "없음" if not leaks else leaks[:5])
    print("내장 데이터:", len(embedded.get("posts", [])), "posts ·",
          len(embedded.get("news", [])), "news ·",
          len(embedded.get("videos", [])), "videos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
