# 노리짱 트래픽센트 v2 · GitHub 배포팩

주요 커뮤니티 · 일간 트렌드 리포트 · 실시간 뉴스 · 유튜브 · 블로그 · 핫딜 · 인디 프로젝트 ·
오픈소스 · 앱·게임 순위 · 해커톤 · AI 벤치마크 · 방문 추이 · 문의 및 제안을 한 화면에서 보는
**노리짱 전용 트래픽 레이더**입니다.

- 서버비 **0원** (GitHub Actions + GitHub Pages 무료)
- 수집 **하루 2회** (`07:00` / `19:00` KST)
- AI 요약 **Gemini Flash 무료 티어** (PC 클로드 한도 사용 안 함)
- 화면은 **단일 HTML** (외부 CDN·웹폰트·외부 이미지 0건, 오프라인에서도 열림)

---

## 1. 폴더 구성

```
.
├── index.html                     # 화면 (data.json 이 없으면 내장 데이터로 동작)
├── data.json                      # 수집 결과 (자동 커밋됨)
├── collector.py                   # 수집·정규화·중복제거·스코어링 (표준 라이브러리만 사용)
├── summarize.py                   # Gemini Flash 요약 + 규칙 기반 대체
├── sources.yaml                   # 수집 소스 정의서 (문서 + 설정)
├── requirements.txt               # 선택 패키지 (비어 있어도 동작)
├── build.py                       # src/ 를 index.html 한 파일로 합치는 빌드 스크립트
├── src/
│   ├── shell.html                 # 화면 뼈대
│   ├── app.css                    # 디자인
│   └── app.js                     # 렌더·필터·검색·스크랩·문의
├── data/
│   ├── issue.json                 # 발행 호수 카운터 (자동)
│   ├── history/YYYY-MM-DD.json    # 지난 호 보관 (자동)
│   └── visits.json                # (선택) 방문 추이 실측값
└── .github/workflows/collect.yml  # 07:00 / 19:00 KST 자동 실행
```

---

## 2. 10분 설정 (처음 한 번만)

### ① 공개 저장소 만들기
1. GitHub → **New repository**
2. 이름 예: `nori-traffic-scent`
3. **Public** 선택 (Pages 무료 조건) → **Create repository**

### ② 파일 올리기
- 이 폴더의 파일 **전체**를 그대로 올립니다. (`.github/workflows/collect.yml` 포함)
- 웹에서 올릴 때: **Add file → Upload files** → 폴더째 드래그 → Commit
- 터미널을 쓸 때:
  ```bash
  git init && git add . && git commit -m "init: 노리짱 트래픽센트 v2"
  git branch -M main
  git remote add origin https://github.com/<아이디>/nori-traffic-scent.git
  git push -u origin main
  ```

### ③ GitHub Pages 켜기
**Settings → Pages → Source: Deploy from a branch → Branch: `main` / `(root)` → Save**
1~2분 뒤 `https://<아이디>.github.io/nori-traffic-scent/` 가 열립니다.

### ④ Actions 쓰기 권한 주기 (data.json 자동 커밋용)
**Settings → Actions → General → Workflow permissions → `Read and write permissions` → Save**

### ⑤ (선택) API 키 등록
**Settings → Secrets and variables → Actions → New repository secret**
| 이름 | 어디서 발급 | 없으면 |
|---|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | 규칙 기반 요약으로 대체 |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | https://developers.naver.com → 애플리케이션 등록 (검색 API) | 네이버 뉴스·블로그·쇼핑·카페 수집 생략 |
| `YOUTUBE_API_KEY` | Google Cloud Console → YouTube Data API v3 사용 설정 → API 키 | 채널 RSS(최신 업로드)로 대체 |
| `DATA_GO_KR_KEY` | https://www.data.go.kr (나라장터 입찰공고·실거래가 활용 신청) | 건축·입찰 피드는 예시 유지 |

> 키가 없어도 **화면은 정상 동작**합니다. 없는 소스만 `collect_log` 에 `key-missing` 으로 남고 나머지는 계속 수집합니다.

### ⑥ 첫 수집 실행
**Actions → collect → Run workflow → Run workflow**
- 1~2분 뒤 초록 체크가 뜨면 `data.json` 이 새로 커밋됩니다.
- Pages 주소를 새로 고치면 헤더 배지가 **`실데이터 연결됨`** 으로 바뀝니다.

---

## 3. 매일 자동으로 도는 일

| 시각(KST) | 무엇을 |
|---|---|
| 07:00 / 19:00 | `collector.py` → 공개 RSS·공개 API 수집 |
| 이어서 | `summarize.py` → Gemini Flash 요약(없으면 규칙 기반) |
| 이어서 | `data.json` 자동 커밋 → Pages 즉시 반영 |

- cron 은 UTC 기준입니다: `0 22 * * *` = 07:00 KST, `0 10 * * *` = 19:00 KST.
- 수집 항목이 25건 미만이면 **직전 data.json 을 덮어쓰지 않습니다**(빈 화면 방지).

---

## 4. 로컬에서 돌려보기

```bash
python3 collector.py      # data.json 생성
python3 summarize.py      # 요약 채우기 (GEMINI_API_KEY 없으면 규칙 기반)
python3 build.py          # src/ → index.html 재빌드
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000/index.html
```

`index.html` 을 파일로 바로 열어도(=`file://`) 내장 데이터로 화면이 뜹니다.
이때 배지는 `샘플 데이터` 로 표시됩니다.

---

## 5. 수집 소스 상태 (2026-11-21 실측)

| 영역 | 소스 | 키 | 상태 |
|---|---|---|---|
| 커뮤니티 | 디시 실시간베스트 · 네이트판 톡커들의 선택 · 더쿠 · 보배드림 | 불필요 | ✅ 수집 |
| 커뮤니티 | 개드립 · 에펨카리아 · 루리웹 · 인스티즈 | 불필요 | ⚠️ 403/차단 → 자동 skip |
| 뉴스 | Google News KR(경제·IT·부동산·사회) · 연합뉴스 · 매일경제 · 전자신문 · AI타임스 | 불필요 | ✅ 수집 |
| 뉴스 | 한국경제 RSS | 불필요 | ⚠️ 403 (skip) |
| 유튜브 | SBS News · YTN · JTBC 채널 RSS | 불필요 | ✅ 수집 |
| 유튜브 | 실시간 인기 급상승 | `YOUTUBE_API_KEY` | 키 있으면 인기순 |
| 블로그 | GeekNews · 슬로우뉴스 · 바이라인네트워크 | 불필요 | ✅ 수집 |
| 핫딜 | 네이버 쇼핑 최저가 + 큐레이션 | `NAVER_*` | 키 없으면 예시 가격 |
| 오픈소스 | GitHub Trending | 불필요 | ✅ 수집 |
| 앱·게임 | Steam 최다 플레이 · Apple 앱스토어 RSS | 불필요 | ✅ 수집 |
| 해커톤 | Devpost Open Hackathons | 불필요 | ✅ 수집 |
| 건축·입찰 | 나라장터 입찰공고 | `DATA_GO_KR_KEY` | 키 필요 |
| AI·부업 | GeekNews · 수집 제목 | 불필요 | ✅ 부분 수집 |
| 맘카페·부동산·앱테크 | 네이버 카페·블로그 검색 | `NAVER_*` | 키 없으면 ‘예시’ 라벨 |

**‘예시’ 배지**는 실제 수집이 아니라 화면 확인용 샘플이라는 표시입니다. 키를 넣으면 하나씩 실데이터로 바뀝니다.

---

## 6. 무료 한도 계산

| 서비스 | 무료 한도 | 이 프로젝트 사용량 |
|---|---|---|
| GitHub Actions | 공개 저장소 무료 | 하루 2회 × 2~3분 ≈ 월 180분 이하 |
| GitHub Pages | 공개 저장소 무료 | 정적 1페이지 |
| Gemini Flash | 무료 티어 (모델별 RPM/RPD) | 하루 2회 호출 |
| 네이버 검색 API | 일 25,000 콜 | 하루 10~20 콜 |
| YouTube Data API v3 | 일 10,000 units | `videos.list`(1 unit) 사용 시 여유 / `search.list`(100 units)도 하루 2회면 200 units |
| 공공데이터포털 | 활용 신청별 일일 한도 | 하루 2~4 콜 |

---

## 7. 자주 막히는 곳

| 증상 | 원인 · 해결 |
|---|---|
| Actions 가 `data.json` 커밋에서 실패 | Settings → Actions → Workflow permissions 를 `Read and write` 로 |
| Pages 가 404 | Settings → Pages 의 Branch 가 `main` / `(root)` 인지, 첫 배포가 끝났는지 확인 |
| 배지가 계속 `샘플 데이터` | Pages 주소로 열었는지(`file://` 아님), `data.json` 이 저장소 루트에 있는지 확인 |
| 특정 소스가 계속 비어 있음 | `data.json` 의 `collect_log` 에서 `status` 확인 (`skip`/`error`/`key-missing`) |
| 커뮤니티 글이 너무 적음 | 사이트가 봇을 막는 경우입니다. 차단을 우회하지 않고 skip 하도록 설계했습니다 |
| 요약이 짧고 투박함 | `GEMINI_API_KEY` 를 넣으면 문장 요약으로 대체됩니다 |

---

## 8. 문의 및 제안

화면 하단 **💬 문의 및 제안** 에서 유형(오류 제보 / 기능 제안 / 소스 추가 요청)과 내용을 저장하면
이 브라우저의 `localStorage` 에 기록되고, **📋 내용 복사** 로 메일·메시지에 붙여 넣을 수 있습니다.
저장소 주소(`site.repo`)가 채워져 있으면 **🐙 GitHub Issue로 등록** 버튼이 바로 이슈 작성 화면을 엽니다.
(GitHub Actions 에서 실행되면 `GITHUB_REPOSITORY` 가 자동으로 들어갑니다.)
