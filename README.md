# 트렌드픽 TrendPick v3 · GitHub 배포팩

커뮤니티 인기글 · 주요 뉴스 · 유튜브 · 블로그 · 특가 소식 · 오픈소스 · 앱·게임 순위 · 해커톤을
한 화면에서 보는 **트렌드 큐레이션 포털**입니다. 매일 두 번 자동 수집한 **실제 데이터만** 보여 줍니다.

- 라이브: **https://econature7-lab.github.io/nori-traffic-scent/**
- 서버비 **0원** (GitHub Actions + GitHub Pages 무료)
- 수집 **하루 2회** (`07:17` / `19:17` KST)
- 화면은 **단일 HTML** (외부 CDN·웹폰트 0건 · `file://` 에서도 열림)
- 저장소 이름(`nori-traffic-scent`)은 기존 링크가 깨지지 않도록 그대로 두고,
  **화면·문서·데이터의 서비스명만 「트렌드픽」으로 전면 교체**했습니다.

---

## 1. 화면 구성

| 영역 | 내용 |
|---|---|
| **DAILY BRIEF** | 오늘의 대표 헤드라인 + 요약 + **클릭 가능한 핫픽 3선**(서로 다른 분야 우선) + 수집 현황 |
| **실시간 급상승 TOP 10** | Google Trends + 수집 제목 키워드. 키워드를 누르면 아래 피드가 즉시 필터 |
| **오늘의 픽 탐색** | 분야 칩(커뮤니티·뉴스·유튜브·블로그·맘카페·부동산·AI·앱테크·건축) + 실시간 검색 + 정렬(인기/급상승/최신) + **⭐ 저장한 픽(localStorage)** |
| 실시간 뉴스 | 분야 탭, 썸네일 카드 |
| 지금 뜨는 영상 | 유튜브 최신 업로드(썸네일 100%) |
| 특가 · 핫딜 | (네이버 쇼핑 키 연결 시) 실제 최저가 / 키가 없으면 오늘 수집된 할인 소식 + **쿠팡 최저가 검색·제휴 고지** (섹션 안에서만 노출) |
| 오픈소스 · 앱·게임 | GitHub 트렌딩, 앱스토어·스팀 순위(앱 아이콘 포함) |
| 해커톤 · 공모전 | Devpost 마감 임박 순 |
| 광고 슬롯 | 상단 리더보드 · 피드 인라인 · 사이드바 · 하단 배너 (4곳, ID만 넣으면 노출) |

디자인은 연한 회백색 파스텔 카드가 아니라 **웜 아이보리 캔버스 + 페이퍼 카드 + 헤어라인 + 딥 미드나잇 잉크**의
에디토리얼 톤입니다. 포인트 컬러는 시그니처 **코랄-로즈 `#E11D48`** 와 **틸 `#0D9488`**, 로고는 커스텀 SVG 마크입니다.

```
--canvas #F7F6F2   --surface #FFFFFF   --line #E6E4DD   --ink #111827
--coral  #E11D48   --teal    #0D9488   --night #101418
```

---

## 2. 폴더 구성

```
.
├── index.html                     # 화면 (data.json 이 없으면 내장 스냅샷으로 동작)
├── og.png                         # 공유 미리보기 이미지(1200×630)
├── about.html · policy.html · privacy.html · contact.html   # 빌드 생성 고정 페이지
├── robots.txt · sitemap.xml       # 빌드 생성 SEO 파일
├── data.json                      # 수집 결과 (Actions 가 자동 커밋)
├── collector.py                   # 수집·썸네일·정규화·중복제거·스코어링 (표준 라이브러리만)
├── summarize.py                   # (선택) Gemini Flash 요약 + 규칙 기반 대체
├── build.py                       # src/ → index.html 한 파일로 합치기
├── check_visual.py                # Playwright 화면 검증(데스크톱·모바일·광고 미리보기)
├── sources.yaml                   # 수집 소스 정의서 (문서 + 설정)
├── src/
│   ├── shell.html                 # 화면 뼈대 · SEO/OG 메타 · SVG 파비콘
│   ├── app.css                    # 디자인 시스템
│   ├── app.js                     # 렌더 · 필터 · 검색 · 저장 · 광고 슬롯 · 제휴 · 글감 키트
│   ├── pages.css                  # 고정 페이지 공용 스타일
│   └── pages/                     # about · policy · privacy · contact 원본(빌드 시 루트로 생성)
├── data/
│   ├── creators.json              # X·블로그 자동화용 경량 JSON (빌드 생성)
│   ├── issue.json                 # 발행 호수 카운터
│   └── history/YYYY-MM-DD.json    # 지난 호 보관
└── .github/workflows/collect.yml  # 07:17 / 19:17 KST 자동 수집 · 빌드 · 커밋
```

---

## 3. 광고 붙이는 방법 (ID만 넣으면 끝)

`src/app.js` 맨 위 **`TRENDPICK_ADS`** 한 곳만 고치면 됩니다.

```js
var TRENDPICK_ADS = {
  enabled: true,
  adsense: {
    client: 'ca-pub-0000000000000000',
    slots: { top: '1111111111', feed: '2222222222', side: '3333333333', bottom: '4444444444' }
  },
  kakao: { unit: 'DAN-xxxxxxxx', width: '320', height: '100' },
  preview: false
};
```

- **구글 애드센스**: `client` + 슬롯별 `data-ad-slot` 값을 넣으면 해당 자리에 `adsbygoogle` 코드가 나갑니다.
- **카카오 애드핏**: `unit` 을 넣으면 `kakao_ad_area` 영역이 나갑니다(피드 인라인 제외).
- **아무 값도 없으면**: 광고 상자는 화면에서 **완전히 사라집니다**(빈 상자 없음).
- **위치 확인**: 푸터의 **[📢 광고 자리 미리보기]** 버튼 또는 주소에 `?ad_preview=1` 을 붙이면
  실제 크기(728×90 / 320×100 / 300×250 / 인피드)대로 자리만 표시됩니다. 미리보기에서는 외부 스크립트를 부르지 않습니다.
- 수정 후 `python build.py` → `index.html` 재생성 → 커밋.

자세한 운영 절차·수익화 체크리스트는 **`downloads/트렌드픽_수익화_운영가이드.md`** 참고.

---

## 3-B. 수익화 연결 (애드센스 준비 · 쿠팡 · 글감 키트)

**애드센스 승인용 고정 페이지** — `build.py` 가 `src/pages/` 원본으로 루트에 생성합니다.

| 파일 | 내용 |
|---|---|
| `about.html` | 소개 · 하루 두 번(07:17/19:17) 수집 구조 · 다섯 분야 |
| `policy.html` | 편집·큐레이션 원칙 · 출처/저작권 · AI 요약 검수/정정 · 광고·제휴 분리 |
| `privacy.html` | 개인정보처리방침 · localStorage · 애드센스/애드핏 쿠키 · 맞춤 광고 해제 · 쿠팡 고지 |
| `contact.html` | 문의 · Issues · 기사 수정/삭제 절차 · 제휴 문의 |
| `robots.txt` · `sitemap.xml` | 전체 허용 + 메인·4개 페이지 sitemap |

`src/shell.html` 의 `<!-- VERIFICATION_META -->` 자리에 서치콘솔·애드센스 확인 메타를 바로 넣을 수 있습니다.

**쿠팡 파트너스** — `src/app.js` 의 `TRENDPICK_AFFILIATE`(coupon ID `AF2392399`)와 `TRENDPICK_DEAL_LINKS`(단축링크 매핑 슬롯)만 채우면 됩니다. 특가·핫딜 영역 안에서만 고지·링크·검색창이 노출되고, 뉴스·커뮤니티·광고 영역은 건드리지 않습니다.

**X·블로그 글감 키트** — 브리프의 `✨ X·블로그 글감 키트` 버튼. X 탭은 금기선(건축·부동산·맘카페·숲체험·정치)을 자동 제외한 IT/AI·생활·앱 소재 5건으로 스레드 뼈대를, 블로그 탭은 목차 없이 `핵심 3줄 요약` + 소제목 3개 + 트렌드픽 유입 링크를 만듭니다. 카드의 `📋` 버튼은 그 카드 한 건을 글감으로 복사합니다.

**경량 피드** — `data/creators.json` (top10 · brief · 분야별 상위 5건 `ai`/`estate`/`mom`/`apptech`/`webtoon`). `지연_X`·블로그 자동화가 그대로 읽어 갈 수 있는 정적 JSON입니다.

**브리프 구성** — `brief` 는 `title`(편집 헤드라인) · `lead`(덱 1~2문장) · `paragraphs`(본문 2~3문단) · `highlights`(핵심 포인트 3줄) · `sections`(분야별 카드) · `picks`(대표 기사)로 이루어집니다. `summarize.py` 는 Gemini 가 있으면 이 구조로 문장을 쓰고, 키가 없으면 같은 구조를 규칙 기반으로 채웁니다. 메인 히어로에는 `lead` 와 `highlights` 가, 그 아래 `#brief-deep` 영역에는 `paragraphs` 와 `sections` 가 그대로 실려 페이지 본문 분량을 만듭니다.

---

## 4. 썸네일 정책과 실측

1. RSS `media:group > media:thumbnail` · `media:content(medium=image)` · `enclosure` · 본문 `<img>` 를 먼저 읽습니다.
2. 유튜브는 URL 에서 `video_id` 를 뽑아 `https://i.ytimg.com/vi/{id}/hqdefault.jpg` 를 **항상** 보장합니다.
3. 이미지가 없는 기사는 `og:image` / `twitter:image` 를 짧은 타임아웃(6초)·동시성 8로 추출하고,
   연속 실패한 호스트는 그 실행에서 건너뜁니다.
4. GitHub 저장소는 `opengraph.githubassets.com`, 앱은 iTunes 아이콘, 스팀은 `header.jpg` 를 씁니다.
5. 그래도 이미지가 없거나 `onerror` 가 나면 **깨진 이미지 대신 분야별 에디토리얼 커버**가 나옵니다
   (딥톤 그라데이션 + 분야 라벨·영문 키커 + 기하 장식, 흰 글자 대비 6.8:1 이상).
   `loading="lazy"`, `referrerpolicy="no-referrer"`, `aspect-ratio:16/9` 통일.

2026-11-22 실측 (`python collector.py` 로그 그대로):

| 구분 | 결과 |
|---|---|
| 유튜브 | **11/11 (100%)** |
| 뉴스 | **32/32 (100%)** |
| 블로그 | 10/10 (100%) |
| 오픈소스·해커톤 | 12/12 (100%) |
| 앱·게임 | 16/16 (100%) |
| 커뮤니티 | 8/16 (50% — 네이트판·더쿠는 대표 이미지가 없는 글) |
| **전체** | **83/97 (86%)** · GitHub Actions 실행에서는 79/97 (81%) — 데이터센터 IP에서 커뮤니티 대표 이미지 일부가 빠집니다 |

---

## 5. 수집 소스 상태 (2026-11-22 실측)

| 영역 | 소스 | 키 | 상태 |
|---|---|---|---|
| 커뮤니티 | 네이트판 톡커들의 선택 · 더쿠 · 보배드림 · 82cook | 불필요 | ✅ 수집 |
| 뉴스 | 매일경제 · 연합뉴스(경제/산업/정치/사회) · 전자신문 · AI타임스 · 조선일보 | 불필요 | ✅ 수집 |
| 유튜브 | SBS 뉴스 · YTN · JTBC 채널 RSS | 불필요 | ✅ 수집 |
| 유튜브 | 실시간 인기 급상승 | `YOUTUBE_API_KEY` | 키 있으면 인기순 |
| 블로그 | GeekNews · 슬로우뉴스 · 바이라인네트워크 · 요즘IT · 벤처스퀘어 | 불필요 | ✅ 수집(+본문·og:image 보강) |
| 오픈소스 | GitHub Trending | 불필요 | ✅ 수집 |
| 앱·게임 | iTunes 앱 순위(아이콘 포함) · Steam 최다 플레이 | 불필요 | ✅ 수집 |
| 해커톤 | Devpost Open Hackathons | 불필요 | ✅ 수집 |
| 핫딜 | 네이버 쇼핑 최저가 | `NAVER_*` | 키 필요(없으면 수집된 할인 소식 + 쿠팡 최저가 검색) |
| 웹툰·엔터 | 네이버웹툰 요일 연재 공개 목록 | 불필요 | ✅ 수집(평점 순 · 19금 제외) |

**정리한 소스 (v3)**

- **한국경제 RSS (403)**: 데이터센터 IP·반복 요청에서 403 이 계속되어 **매일경제 + 연합뉴스 경제**로 대체했습니다(둘 다 대표 이미지 포함). `collect_log` 에 `replaced` 로 기록됩니다.
- **Apple 앱스토어 RSS 타임아웃**: 1차를 **iTunes 순위 JSON**(아이콘 포함 · 0.3초)으로 바꾸고 마케팅 RSS 는 예비로 두었습니다.
- **인스티즈 제목 미검출**: 목록이 JS 로 그려져 HTML 에 제목이 없습니다. **82cook** 으로 교체했습니다.
- 개드립(403) · 에펨코리아(430) · 루리웹(타임아웃) · 클리앙(JS) · 뽐뿌(403)도 같은 이유로 제외했습니다.
- **예시(샘플) 데이터는 전부 제거**했습니다. 수집이 없는 날은 섹션이 접히거나 빈 상태 문구가 나옵니다.

---

## 6. 10분 설정 (처음 한 번만)

1. **저장소**: `econature7-lab/nori-traffic-scent` (Public, Pages 무료 조건)
2. **파일 올리기**: 이 폴더의 파일 전체 업로드 (`.github/workflows/collect.yml` 포함)
3. **Pages**: Settings → Pages → Deploy from a branch → `main` / `(root)`
4. **Actions 권한**: Settings → Actions → General → Workflow permissions → `Read and write`
5. **(선택) API 키**: Settings → Secrets and variables → Actions

| 이름 | 어디서 | 없으면 |
|---|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | 규칙 기반 브리프 |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | https://developers.naver.com (검색 API) | 네이버 뉴스·블로그·쇼핑 생략 |
| `YOUTUBE_API_KEY` | Google Cloud Console → YouTube Data API v3 | 채널 RSS |
| `DATA_GO_KR_KEY` | https://www.data.go.kr | 나라장터 생략 |

6. **첫 수집**: Actions → collect → Run workflow

---

## 7. 매일 자동으로 도는 일

| 시각(KST) | 무엇을 |
|---|---|
| 07:17 / 19:17 | `collector.py` → 공개 RSS·API 수집 (썸네일 보강 포함, 약 40초) |
| 이어서 | `summarize.py` → Gemini 요약(없으면 규칙 기반 그대로) |
| 이어서 | `build.py` → `index.html` + 고정 페이지 4종 + `robots.txt`/`sitemap.xml` + `data/creators.json` |
| 이어서 | `data.json` · `data/` · `index.html` · 고정 페이지 자동 커밋 → Pages 반영 |

수집 항목이 25건 미만이면 **직전 data.json 을 덮어쓰지 않습니다**(빈 화면 방지).

---

## 8. 로컬에서 돌려보기

```bash
python3 collector.py      # data.json 생성 (약 40초)
python3 summarize.py      # (선택) 요약
python3 build.py          # src/ → index.html
python3 -m http.server 8000
# http://localhost:8000/index.html
```

검증(로컬 Chromium):

```bash
python3 check_visual.py        # 데스크톱 1440×900 · 모바일 390×844 · ?ad_preview=1
python3 check_monetization.py  # 글감 키트·쿠팡 제휴(픽스처)·고정 페이지 4종·내비 왕복
```

---

## 9. 검증 결과 (2026-11-22)

| 항목 | 데스크톱 1440×900 | 모바일 390×844 |
|---|---|---|
| 콘솔 오류 | 0건 | 0건 |
| 페이지 오류 | 0건 | 0건 |
| 깨진 이미지(`naturalWidth===0`) | 0건 (51장 전부 로드) | 0건 (51장 전부 로드) |
| 가로 넘침 | 0건 | 0건 |
| 광고 미리보기 | 슬롯 3 + 인피드 1 표시 | 동일 |
| 글감 키트 | X·블로그·공유 탭 전환·복사 정상, 금기어 0건 | 모달 동일 |
| 고정 페이지 4종 | 200 OK · 오류 0 · 넘침 0 | 390px 넘침 0 |

---

## 10. 자주 막히는 곳

| 증상 | 원인 · 해결 |
|---|---|
| Actions 가 커밋에서 실패 | Settings → Actions → Workflow permissions `Read and write` |
| Pages 404 | Settings → Pages 의 Branch `main` / `(root)`, 첫 배포 완료 여부 |
| 썸네일이 일부 안 보임 | 그 기사에 대표 이미지가 없는 경우입니다. 일러스트 카드로 대체됩니다 |
| 특정 소스가 계속 비어 있음 | `data.json` 의 `collect_log` 에서 `status` 확인 |
| 광고가 안 나옴 | `TRENDPICK_ADS` 에 client/unit 과 슬롯 ID를 넣고 `build.py` 재실행 |
| 검색이 안 됨 | `index.html` 을 `file://` 로 열면 data.json 을 못 읽습니다 → 로컬 서버 또는 Pages 주소 사용 |
