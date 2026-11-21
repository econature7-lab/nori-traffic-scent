#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
트렌드픽(TrendPick) v3 · build.py
==================================
src/shell.html + src/app.css + src/app.js + data.json 을 하나의 오프라인 HTML로 합칩니다.

  python build.py
    → work/nori-traffic-scent/index.html          (GitHub Pages 배포용)
    → downloads/트렌드픽_v3.html                   (단독 실행본 · 사용자에게 보여줄 파일)

외부 CDN·웹폰트 의존 0건 / 내장 데이터로 file:// 에서도 즉시 동작.
(광고 ID를 넣은 경우에만 애드센스·애드핏 스크립트를 그때 불러옵니다.)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WS = ROOT.parents[1]              # /workspace
SRC = ROOT / "src"
OUT_LOCAL = ROOT / "index.html"
OUT_DOWNLOAD = WS / "downloads" / "트렌드픽_v3.html"

KEEP_KEYS = [
    "schema", "generated_at", "issue", "stats", "sources", "youtube_mode", "site",
    "posts", "news", "videos", "blogs", "deals", "opensource", "apps", "hackathons",
    "ranks", "brief", "thumbs", "collect_log", "notes",
]

AD_HOSTS = ("pagead2.googlesyndication.com", "t1.daumcdn.net")


def main() -> int:
    shell = (SRC / "shell.html").read_text(encoding="utf-8")
    css = (SRC / "app.css").read_text(encoding="utf-8")
    js = (SRC / "app.js").read_text(encoding="utf-8")

    data_path = ROOT / "data.json"
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

    # 외부 의존 점검 (광고 스크립트는 ID를 넣었을 때만 로드되는 선택 사항)
    external_patterns = [
        r'<script[^>]+src=["\'](https?://[^"\']+)',
        r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\'](https?://[^"\']+)',
        r'@import\s+url\(["\']?(https?://[^)"\']+)',
        r'<img[^>]+src=["\'](https?://[^"\']+)',
    ]
    found = []
    for pat in external_patterns:
        found.extend(re.findall(pat, html, re.I))
    found = [u for u in found if not any(h in u for h in AD_HOSTS)]
    print("외부 리소스 참조:", "없음" if not found else sorted(set(found))[:5])

    # 남은 서비스명 점검
    legacy = len(re.findall(r"트래픽센트|Traffic Scent|trafficscent", html, re.I))
    print("구 서비스명 잔존:", legacy, "건")
    print("내장 데이터:", len(embedded.get("posts", [])), "posts ·",
          len(embedded.get("news", [])), "news ·",
          len(embedded.get("videos", [])), "videos ·",
          len(embedded.get("blogs", [])), "blogs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
