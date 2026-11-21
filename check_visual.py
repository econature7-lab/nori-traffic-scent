#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""트렌드픽 v3 · Playwright 검증 (데스크톱/모바일 · 일반/광고 미리보기)"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = "/workspace/pw-browsers/chromium-1255/chrome-linux64/chrome"
os.environ["LD_LIBRARY_PATH"] = Path("/workspace/tmp/browserlibs/libdirs.txt").read_text()

WS = Path("/workspace")
SITE = WS / "work/nori-traffic-scent"
OUT = WS / "downloads"
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}/index.html"


def wait_server():
    for _ in range(40):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/index.html", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


MEASURE = """() => {
  const vw = document.documentElement.clientWidth;
  const inScroll = el => {
    let n = el.parentElement;
    while (n && n !== document.body) {
      const s = getComputedStyle(n);
      if (/auto|scroll|hidden/.test(s.overflowX)) return true;
      n = n.parentElement;
    }
    return false;
  };
  const bad = [];
  document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.right > vw + 1 && !inScroll(el)) {
      bad.push((typeof el.className === 'string' ? el.className : el.tagName) + ' @' + Math.round(r.right));
    }
  });
  const imgs = Array.from(document.images).filter(i => i.getAttribute('src'));
  const loaded = imgs.filter(i => i.complete && i.naturalWidth > 0);
  const broken = imgs.filter(i => i.complete && i.naturalWidth === 0).map(i => i.src);
  const pending = imgs.filter(i => !i.complete).length;
  return {
    docWidth: document.documentElement.scrollWidth,
    clientWidth: vw,
    overflow: bad.slice(0, 10),
    overflowCount: bad.length,
    images: imgs.length,
    imagesLoaded: loaded.length,
    imagesPending: pending,
    broken: broken.slice(0, 10),
    brokenCount: broken.length,
    top10: document.querySelectorAll('#top10List .top10-item').length,
    cards: document.querySelectorAll('#feedGrid .pick').length,
    inlineAd: document.querySelectorAll('#feedGrid .pick-ad').length,
    adSlotsOn: Array.from(document.querySelectorAll('.ad-slot')).filter(e => e.classList.contains('on')).length,
    adSlotHeights: Array.from(document.querySelectorAll('.ad-slot.on')).map(e => Math.round(e.getBoundingClientRect().height)),
    news: document.querySelectorAll('#newsList .news-item').length,
    yt: document.querySelectorAll('#ytRail .yt-card').length,
    deals: document.querySelectorAll('#dealGrid .deal').length,
    os: document.querySelectorAll('#osList .os-item').length,
    apps: document.querySelectorAll('#appList .app-item').length,
    hacks: document.querySelectorAll('#hackList .hack').length,
    mode: (document.querySelector('#statLive') || {}).textContent,
    h1: (document.querySelector('#bTitle') || {}).textContent,
    pickRows: document.querySelectorAll('#bPicks .pick-row').length,
    pageHeight: document.body.scrollHeight
  };
}"""


def check(pw, name, width, height, url, shot):
    res = {"case": name, "url": url, "viewport": f"{width}x{height}"}
    browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--font-render-hinting=none"])
    ctx = browser.new_context(viewport={"width": width, "height": height},
                              device_scale_factor=1, locale="ko-KR",
                              timezone_id="Asia/Seoul",
                              user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"))
    page = ctx.new_page()
    console_errors, page_errors, failed = [], [], []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("requestfailed", lambda r: failed.append(f"{r.url[:90]} {r.failure}"))

    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("#feedGrid .pick", timeout=20000)

    # 지연 로딩 이미지를 모두 요청하고, 스크롤 애니메이션은 끈 상태로 훑습니다.
    page.evaluate("""() => {
      document.documentElement.style.scrollBehavior = 'auto';
      document.querySelectorAll('img[loading="lazy"]').forEach(i => { i.loading = 'eager'; });
    }""")
    page.evaluate("""async () => {
      const step = Math.round(window.innerHeight * 0.9);
      for (let y = 0; y < document.body.scrollHeight; y += step) {
        window.scrollTo(0, y); await new Promise(r => setTimeout(r, 220));
      }
      window.scrollTo(0, 0);
    }""")
    for _ in range(24):
        state = page.evaluate("() => Array.from(document.images).filter(i=>i.getAttribute('src') && !i.complete).length")
        if state == 0:
            break
        page.wait_for_timeout(500)
    page.wait_for_timeout(600)

    data = page.evaluate(MEASURE)
    data["title"] = page.title()

    # 상단 뷰포트 캡처 → 이후 상호작용 테스트
    page.screenshot(path=str(shot), full_page=False)
    full = shot.with_name(shot.stem + "_full" + shot.suffix)
    page.screenshot(path=str(full), full_page=True)

    page.click("#feedGrid .pick .pick-save")
    page.wait_for_timeout(300)
    saved_after = page.text_content("#savedN")
    page.click("#savedBtn")
    page.wait_for_timeout(400)
    saved_only_cards = page.eval_on_selector_all("#feedGrid .pick", "els => els.length")
    page.click("#savedBtn")
    page.wait_for_timeout(250)
    page.fill("#q", "AI")
    page.wait_for_timeout(400)
    search_note = page.text_content("#resultNote")
    page.fill("#q", "")
    page.wait_for_timeout(250)
    page.click("#top10List .top10-item")
    page.wait_for_timeout(400)
    kw_note = page.text_content("#resultNote")

    res.update(data)
    res.update({
        "savedAfterClick": saved_after,
        "savedOnlyCards": saved_only_cards,
        "searchNote": (search_note or "").strip(),
        "keywordNote": (kw_note or "").strip(),
        "consoleErrors": console_errors,
        "pageErrors": page_errors,
        "requestFailed": [f for f in failed if "favicon" not in f],
        "shot": str(shot), "fullShot": str(full),
    })
    ctx.close()
    browser.close()
    return res


def main():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=str(SITE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_server():
            print("서버 시작 실패")
            return 1
        shots = {
            "desktop": OUT / "트렌드픽_v3_데스크톱.png",
            "mobile": OUT / "트렌드픽_v3_모바일.png",
            "desktop_ad": OUT / "트렌드픽_v3_광고미리보기.png",
            "mobile_ad": OUT / "트렌드픽_v3_광고미리보기_모바일.png",
        }
        cases = [
            ("desktop", 1440, 900, BASE),
            ("mobile", 390, 844, BASE),
            ("desktop_ad", 1440, 900, BASE + "?ad_preview=1"),
            ("mobile_ad", 390, 844, BASE + "?ad_preview=1"),
        ]
        results = []
        with sync_playwright() as pw:
            for name, w, h, url in cases:
                results.append(check(pw, name, w, h, url, shots[name]))
        print(json.dumps(results, ensure_ascii=False, indent=2))
        (WS / "tool-results").mkdir(exist_ok=True)
        (WS / "tool-results" / "trendpick_v3_check.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    finally:
        srv.terminate()


if __name__ == "__main__":
    sys.exit(main())
