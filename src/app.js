/* =========================================================
   노리짱 트래픽센트 v2 · app.js
   데이터 구동 렌더 · 필터 · 검색 · 스크랩 · 모달 · 문의
   외부 라이브러리 0개
   ========================================================= */
(function () {
  'use strict';

  var $ = function (s, el) { return (el || document).querySelector(s); };
  var $$ = function (s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); };
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function nfmt(n) { return Number(n || 0).toLocaleString('ko-KR'); }
  function compact(n) {
    n = Number(n || 0);
    if (n >= 100000000) return (n / 100000000).toFixed(1).replace('.0', '') + '억';
    if (n >= 10000) return (n / 10000).toFixed(1).replace('.0', '') + '만';
    if (n >= 1000) return (n / 1000).toFixed(1).replace('.0', '') + 'K';
    return String(n);
  }
  function won(n) { return nfmt(n) + '원'; }
  function todayStamp() {
    var d = new Date(), p = function (v) { return String(v).padStart(2, '0'); };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
  }
  function hashHue(str) {
    var h = 0;
    for (var i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) % 360;
    return h;
  }

  var toastTimer = null;
  function toast(msg) {
    var t = $('#toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove('show'); }, 2400);
  }

  /* ---------------- 데이터 ---------------- */
  var EMBEDDED = { posts: [], news: [], videos: [], blogs: [], deals: [], opensource: [],
                   apps: [], hackathons: [], indie: [], ranks: {}, brief: {}, visits: { days: [] } };
  try {
    var raw = $('#embeddedData').textContent || '{}';
    EMBEDDED = Object.assign(EMBEDDED, JSON.parse(raw));
  } catch (e) { /* 내장 데이터가 깨져도 화면은 계속 */ }

  var DATA = EMBEDDED;
  var MODE = 'sample';

  var CAT = {
    all:     { label: '전체',        cls: 'c-all',     hue: 38 },
    comm:    { label: '일반커뮤니티', cls: 'c-comm',   hue: 215, emoji: '💬' },
    news:    { label: '실시간뉴스',  cls: 'c-news',  hue: 205, emoji: '📰' },
    youtube: { label: '유튜브',      cls: 'c-yt',    hue: 358, emoji: '▶️' },
    mom:     { label: '맘카페·육아', cls: 'c-mom',   hue: 345, emoji: '🌿' },
    estate:  { label: '부동산·경매', cls: 'c-estate',hue: 222, emoji: '🏢' },
    ai:      { label: 'AI·부업',     cls: 'c-ai',    hue: 262, emoji: '🤖' },
    apptech: { label: '앱테크·핫딜', cls: 'c-apptech',hue: 152, emoji: '💰' },
    build:   { label: '건축·입찰',   cls: 'c-build', hue: 38,  emoji: '📐' },
    itai:    { label: 'IT·AI',       cls: 'c-ai',    hue: 262, emoji: '🤖' },
    econ:    { label: '경제·증시',   cls: 'c-estate',hue: 222, emoji: '📈' },
    social:  { label: '사회·생활',   cls: 'c-news',  hue: 205, emoji: '🧾' },
    web:     { label: '블로그',      cls: 'c-comm',  hue: 200, emoji: '✏️' }
  };

  var FEED_TABS = ['all', 'comm', 'news', 'youtube', 'mom', 'estate', 'ai', 'apptech', 'build'];

  var state = {
    cat: 'all', sort: 'hot', query: '', keyword: '', expanded: false,
    rankTab: 'all', newsTab: '전체', ytTab: 'all', indieTab: 'all',
    appTab: '', benchTab: '지능', feedLimit: 12
  };

  /* ---------------- localStorage ---------------- */
  var LS_SCRAP = 'noriTrafficScraps_v2';
  var LS_INQ = 'noriTrafficInquiries_v1';

  function loadJSON(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      if (!raw) return fallback;
      var v = JSON.parse(raw);
      return Array.isArray(v) ? v : (v && Array.isArray(v.items) ? v.items : fallback);
    } catch (e) { return fallback; }
  }
  function saveJSON(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); return true; }
    catch (e) { toast('저장 공간을 쓸 수 없어 이번 화면에서만 유지됩니다'); return false; }
  }

  var scraps = loadJSON(LS_SCRAP, []);
  var inquiries = loadJSON(LS_INQ, []);

  /* ---------------- 통합 피드 만들기 ---------------- */
  function normalizeFeed() {
    var feed = [];
    (DATA.posts || []).forEach(function (p) {
      feed.push({
        id: p.id, cat: p.cat || 'comm', source: p.source || '커뮤니티', title: p.title,
        url: p.url || '', time: p.time || '최근', hot: p.hot || 50, rise: p.rise || 100,
        comments: p.comments || 0, views: p.views || 0,
        keywords: p.keywords || [], summary: p.summary || '',
        sample: !!p.sample, thumb: p.thumb || { hue: hashHue(p.title || ''), variant: 0 },
        meta: p.meta || null, kind: 'post'
      });
    });
    (DATA.news || []).forEach(function (n) {
      if (n.noise) return;   // 연예·스포츠는 통합 피드에서 제외
      feed.push({
        id: n.id, cat: 'news', source: n.source || '뉴스', title: n.title,
        url: n.url || '', time: n.time || '', hot: n.hot || 50, rise: n.rise || 100,
        comments: 0, views: 0, keywords: n.keywords || [], summary: '',
        sample: !!n.sample, thumb: n.thumb || { hue: hashHue(n.title || ''), variant: 1 },
        meta: { section: n.section }, kind: 'news'
      });
    });
    (DATA.videos || []).forEach(function (v) {
      feed.push({
        id: v.id, cat: 'youtube', source: v.channel || 'YouTube', title: v.title,
        url: v.url || '', time: v.time || '', hot: v.hot || 50, rise: v.rise || 100,
        comments: 0, views: v.views || 0, keywords: [], summary: '',
        sample: !!v.sample, thumb: { hue: hashHue(v.title || ''), variant: 2 },
        meta: { kind: v.kind, rank: v.rank }, kind: 'video'
      });
    });
    return feed;
  }
  var FEED = normalizeFeed();

  function feedItem(id) {
    for (var i = 0; i < FEED.length; i++) if (FEED[i].id === id) return FEED[i];
    return null;
  }

  /* ---------------- 스크랩 ---------------- */
  function findScrap(id) {
    for (var i = 0; i < scraps.length; i++) if (scraps[i].id === id) return scraps[i];
    return null;
  }
  function dealById(id) {
    var list = DATA.deals || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  }
  function sourceInfo(id) {
    var f = feedItem(id);
    if (f) return { type: 'post', title: f.title, source: f.source, meta: (CAT[f.cat] || {}).label || '', url: f.url };
    var d = dealById(id);
    if (d) return { type: 'deal', title: d.name, source: d.store, meta: (d.off || 0) + '% 할인 · ' + won(d.price), url: d.url || '' };
    return null;
  }
  function toggleScrap(id) {
    var i = -1;
    for (var k = 0; k < scraps.length; k++) if (scraps[k].id === id) { i = k; break; }
    if (i >= 0) {
      scraps.splice(i, 1); saveJSON(LS_SCRAP, scraps); refreshScrap(); renderFeed(); renderDeals();
      toast('스크랩을 해제했습니다'); return false;
    }
    var info = sourceInfo(id);
    if (!info) return false;
    scraps.unshift({ id: id, type: info.type, title: info.title, source: info.source,
                     meta: info.meta, url: info.url, memo: '', savedAt: new Date().toISOString() });
    saveJSON(LS_SCRAP, scraps); refreshScrap(); renderFeed(); renderDeals();
    toast('스크랩했습니다 · 스크랩함에서 볼 수 있어요');
    return true;
  }

  function refreshScrap() {
    var n = scraps.length;
    ['#scrapCount', '#scrapCount2', '#scrapCount3'].forEach(function (sel) {
      var el = $(sel); if (el) el.textContent = n;
    });
    var prev = $('#scrapPreview');
    if (!prev) return;
    if (!n) {
      prev.innerHTML = '<div class="side-empty">아직 스크랩한 소재가 없습니다.<br>카드의 <b>⭐</b> 또는 핫딜의 <b>🎬</b>를 눌러 보세요.</div>';
      return;
    }
    prev.innerHTML = scraps.slice(0, 3).map(function (s) {
      return '<div class="scrap-item"><span class="si-emoji" aria-hidden="true">' + (s.type === 'deal' ? '🎬' : '⭐') + '</span>' +
        '<span><span class="si-title">' + esc(s.title) + '</span>' +
        '<span class="si-meta">' + esc(s.source) + (s.memo ? ' · 메모 있음' : '') + '</span></span></div>';
    }).join('') + (n > 3 ? '<div class="si-meta" style="text-align:center">외 ' + (n - 3) + '건</div>' : '');
  }

  /* ---------------- 썸네일 (인라인 SVG 아트) ---------------- */
  function thumbArt(hue, variant) {
    var h1 = hue, h2 = (hue + 42) % 360;
    var shapes = '';
    if (variant === 0) {
      shapes = '<circle cx="82%" cy="24%" r="30%" fill="hsl(' + h2 + ' 90% 88%)" opacity=".85"/>' +
               '<circle cx="18%" cy="82%" r="22%" fill="hsl(' + h2 + ' 85% 82%)" opacity=".7"/>' +
               '<rect x="26%" y="46%" width="42%" height="10%" rx="4" fill="hsl(' + h2 + ' 60% 97%)" opacity=".65"/>';
    } else if (variant === 1) {
      shapes = '<path d="M0 70 Q 25 46 50 62 T 100 54 V100 H0 Z" fill="hsl(' + h2 + ' 85% 90%)" opacity=".9"/>' +
               '<path d="M0 82 Q 30 62 58 74 T 100 68 V100 H0 Z" fill="hsl(' + h2 + ' 80% 84%)" opacity=".75"/>' +
               '<circle cx="76%" cy="28%" r="18%" fill="#fff" opacity=".5"/>';
    } else if (variant === 2) {
      shapes = '<rect x="0" y="0" width="100%" height="100%" fill="hsl(' + h2 + ' 90% 95%)" opacity=".55"/>' +
               '<rect x="8%" y="18%" width="34%" height="8%" rx="3" fill="#fff" opacity=".7"/>' +
               '<rect x="8%" y="32%" width="52%" height="6%" rx="3" fill="#fff" opacity=".55"/>' +
               '<circle cx="78%" cy="72%" r="13%" fill="hsl(' + h1 + ' 80% 88%)" opacity=".9"/>';
    } else {
      shapes = '<g opacity=".55">' + [0, 1, 2, 3].map(function (i) {
        return '<rect x="' + (12 + i * 22) + '%" y="' + (18 + (i % 2) * 16) + '%" width="14%" height="' + (34 + i * 8) + '%" rx="6" fill="hsl(' + (h1 + i * 12) + ' 85% 88%)"/>';
      }).join('') + '</g>';
    }
    return '<svg class="art" viewBox="0 0 100 62" preserveAspectRatio="none" aria-hidden="true">' +
      '<defs><linearGradient id="g' + hue + variant + '" x1="0" y1="0" x2="1" y2="1">' +
      '<stop offset="0" stop-color="hsl(' + h1 + ' 90% 93%)"/><stop offset="1" stop-color="hsl(' + h2 + ' 85% 97%)"/>' +
      '</linearGradient></defs><rect width="100" height="62" fill="url(#g' + hue + variant + ')"/>' + shapes + '</svg>';
  }

  /* ---------------- 커뮤니티 필터 · 그리드 ---------------- */
  function matchesQuery(item, q) {
    if (!q) return true;
    q = q.toLowerCase();
    var hay = [item.title, item.source, (item.keywords || []).join(' '), (CAT[item.cat] || {}).label]
      .join(' ').toLowerCase();
    return hay.indexOf(q) !== -1;
  }

  function currentFeed() {
    var q = state.query.trim();
    var list = FEED.filter(function (f) {
      if (state.cat !== 'all' && f.cat !== state.cat) return false;
      if (!matchesQuery(f, q)) return false;
      return true;
    });
    list.sort(function (a, b) {
      return state.sort === 'rising' ? (b.rise || 0) - (a.rise || 0) : (b.hot || 0) - (a.hot || 0);
    });
    return list;
  }

  function feedCard(f, idx) {
    var m = CAT[f.cat] || CAT.comm;
    var on = !!findScrap(f.id);
    var sc = findScrap(f.id);
    var hue = (f.thumb && typeof f.thumb.hue === 'number') ? f.thumb.hue : m.hue;
    var variant = (f.thumb && f.thumb.variant) || 0;
    var glyph = f.kind === 'video' ? '' : (m.emoji || '💬');
    var flag = f.sample ? '<span class="flag">예시</span>'
      : (f.kind === 'video' ? '<span class="flag">' + (f.meta && f.meta.kind === 'shorts' ? 'SHORTS' : '영상') + '</span>' : '');
    var metaBits = [];
    if (f.kind === 'post') {
      if (f.comments) metaBits.push('💬 ' + nfmt(f.comments));
      if (f.views) metaBits.push('👁 ' + compact(f.views));
    } else if (f.kind === 'video') {
      if (f.views) metaBits.push('👁 ' + compact(f.views));
    }
    metaBits.push('▲' + (f.rise || 0) + '%');
    metaBits.push(f.time || '');
    return '<article class="feed" data-id="' + esc(f.id) + '" data-testid="feed-' + esc(f.id) + '">' +
      '<div class="thumb" style="--h:' + hue + '">' + thumbArt(hue, variant) +
        '<span class="glyph" aria-hidden="true">' + glyph + '</span>' +
        '<span class="badge-src">' + esc(f.source) + '</span>' + flag +
        (f.kind === 'video' ? '<span class="play" aria-hidden="true">▶</span>' : '') +
      '</div>' +
      '<div class="feed-body">' +
        '<h3 class="feed-title">' + esc(f.title) + '</h3>' +
        '<div class="feed-meta">' + metaBits.filter(Boolean).map(function (b, i) {
          return (i ? '<span class="dot" aria-hidden="true"></span>' : '') + '<span>' + esc(b) + '</span>';
        }).join('') + '</div>' +
        '<div class="feed-actions">' +
          '<button class="act js-scrap' + (on ? ' on' : '') + '" type="button" data-id="' + esc(f.id) + '" ' +
            'aria-pressed="' + on + '" data-testid="scrap-' + esc(f.id) + '"><span class="ico" aria-hidden="true">⭐</span>스크랩</button>' +
          '<button class="act js-memo' + (sc && sc.memo ? ' on' : '') + '" type="button" data-id="' + esc(f.id) + '" ' +
            'data-testid="memo-' + esc(f.id) + '"><span class="ico" aria-hidden="true">✍️</span>메모</button>' +
        '</div>' +
      '</div></article>';
  }

  function renderFeed() {
    var box = $('#feedGrid');
    var list = currentFeed();
    var shown = state.expanded ? list : list.slice(0, state.feedLimit);
    box.innerHTML = shown.map(feedCard).join('') ||
      '<div class="empty"><b>조건에 맞는 글이 없습니다</b>' +
      (state.query ? '‘' + esc(state.query) + '’ 검색 결과가 비어 있습니다.' : '다른 분야를 골라 보세요.') + '</div>';

    var note = $('#resultNote');
    if (state.query) note.innerHTML = '‘<b>' + esc(state.query) + '</b>’ 검색 결과 <b>' + list.length + '</b>건';
    else if (state.cat !== 'all') note.innerHTML = esc((CAT[state.cat] || {}).label) + ' <b>' + list.length + '</b>건';
    else note.innerHTML = '통합 피드 <b>' + list.length + '</b>건 · ' + (state.sort === 'rising' ? '급상승 순' : '인기 순');

    var more = $('#moreBtn');
    if (list.length > state.feedLimit) {
      more.hidden = false;
      more.textContent = state.expanded ? '접기' : '더 보기 (' + list.length + '건)';
    } else more.hidden = true;

    var chip = $('#kwChip');
    if (state.keyword) { chip.hidden = false; $('#kwChipText').textContent = '#' + state.keyword; }
    else chip.hidden = true;
  }

  function renderCatChips() {
    $('#catChips').innerHTML = FEED_TABS.map(function (key) {
      var m = CAT[key];
      return '<button class="chip" type="button" role="tab" data-cat="' + key + '" data-testid="cat-' + key + '" ' +
        'aria-selected="' + (state.cat === key) + '">' + esc(m.label) + '</button>';
    }).join('');
  }

  /* ---------------- 랭킹 ---------------- */
  var RANK_TABS = [['all', '전체'], ['comm', '커뮤니티'], ['news', '뉴스'], ['youtube', '유튜브'],
                   ['mom', '맘카페'], ['estate', '부동산'], ['ai', 'AI·부업']];

  function renderRankTabs() {
    $('#rankTabs').innerHTML = RANK_TABS.map(function (t) {
      return '<button class="rtab" type="button" role="tab" data-rank="' + t[0] + '" ' +
        'aria-selected="' + (state.rankTab === t[0]) + '">' + t[1] + '</button>';
    }).join('');
  }

  function renderRank() {
    var ranks = DATA.ranks || {};
    var list = ranks[state.rankTab] || ranks.all || [];
    if (!list.length) { $('#rankList').innerHTML = '<li class="side-empty">수집된 키워드가 없습니다</li>'; }
    else {
      var max = list.reduce(function (a, b) { return Math.max(a, b.r || 0); }, 1);
      $('#rankList').innerHTML = list.slice(0, 7).map(function (item, i) {
        var w = Math.max(6, Math.round((item.r || 0) / max * 100));
        return '<li><button class="rank-item" type="button" data-kw="' + esc(item.k) + '" data-testid="rank-kw-' + i + '">' +
          '<span class="rk-no">' + (i + 1) + '</span>' +
          '<span class="rk-body"><span class="rk-kw">' + esc(item.k) + '</span>' +
          '<span class="rk-bar"><i style="width:' + w + '%"></i></span></span>' +
          '<span class="rk-up">▲' + (item.r || 0) + '%</span></button></li>';
      }).join('');
    }

    var top = FEED.filter(function (f) { return f.kind === 'post'; })
      .sort(function (a, b) { return (b.hot || 0) - (a.hot || 0); }).slice(0, 3);
    $('#rankExtra').innerHTML = top.map(function (f, i) {
      return '<button class="re-item" type="button" data-kw="' + esc((f.keywords || [])[0] || f.title.slice(0, 12)) + '">' +
        '<span class="re-no">' + (i + 1) + '</span><span>' +
        '<span class="re-title">' + esc(f.title) + '</span>' +
        '<span class="re-meta">' + esc(f.source) + ' · ' + (CAT[f.cat] || {}).label + '</span></span></button>';
    }).join('');
  }

  /* ---------------- 리포트(브리프) ---------------- */
  function renderBrief() {
    var b = DATA.brief || {};
    var issue = DATA.issue || {};
    var sections = b.sections || [];
    $('#briefNo').textContent = b.no || ('No.' + String(issue.no || 1).padStart(2, '0'));
    $('#briefDate').textContent = b.label || issue.label || '';
    $('#briefEyebrow').textContent = '오늘의 트렌드 리포트 · ' + (b.date || issue.date || '') +
      (b.engine ? '' : '');
    $('#briefTitle').textContent = b.title || '오늘의 트렌드 리포트';
    $('#briefLead').textContent = b.lead || '';
    $('#heroIssueNo').textContent = issue.label || b.label || 'No.01';
    $('#briefEngine').textContent = b.engine ? ('요약: ' + (b.engine.indexOf('gemini') === 0 ? 'Gemini Flash' : '규칙 기반')) : '';

    $('#briefChips').innerHTML = sections.slice(0, 5).map(function (s) {
      return '<span class="chip-sm">' + esc(s.label || '') + '</span>';
    }).join('');

    var metrics = b.metrics || {};
    var st = DATA.stats || {};
    var mvals = [
      ['심층 이슈', (metrics.deep || sections.length || 0) + '건'],
      ['수집 출처', (st.live_sources || st.sources || 0) + '곳'],
      ['수집 글', (st.collected || FEED.length) + '건']
    ];
    $('#briefMetrics').innerHTML = mvals.map(function (m) {
      return '<div class="mcard"><small>' + m[0] + '</small><b class="up">' + m[1] + '</b></div>';
    }).join('');
    $('#briefThumbMetrics').innerHTML = [['수집 출처', mvals[1][1]], ['핵심 이슈', mvals[0][1]]]
      .map(function (m) { return '<div>' + m[0] + '<b>' + m[1] + '</b></div>'; }).join('');
  }

  function briefBody(b) {
    var eng = b.engine || '';
    var secs = (b.sections || []).map(function (s) {
      var m = CAT[s.key] || CAT.comm;
      return '<div class="brief-section"><h4><span class="badge-cat">' + esc(s.label || m.label) + '</span>' +
        esc(s.title || '') + '</h4><p>' + esc(s.body || '') + '</p>' +
        ((s.points || []).length ? '<ul class="mb-list">' + s.points.map(function (p) {
          return '<li>' + esc(p) + '</li>';
        }).join('') + '</ul>' : '') + '</div>';
    }).join('');
    var note = eng.indexOf('gemini') === 0
      ? '※ Gemini Flash가 수집 목록을 요약했습니다. 원문은 각 카드의 링크에서 확인하세요.'
      : '※ AI 키가 없어 규칙 기반으로 정리했습니다. GEMINI_API_KEY를 넣으면 문장 요약으로 대체됩니다.';
    return '<p class="mb-p">' + esc(b.lead || '') + '</p>' + secs +
      '<p class="micro-note" style="margin-top:10px">' + note + '</p>';
  }

  function openBrief() {
    var b = DATA.brief || {};
    openModal({
      eyebrow: 'DAILY BRIEF · ' + (b.no || ''),
      title: '오늘의 트렌드 리포트 · ' + (b.date || ''),
      body: briefBody(b),
      foot: '<button class="btn btn-amber" type="button" id="briefToFeed">이 리포트 소재로 피드 보기</button>' +
            '<button class="btn" type="button" data-close>닫기</button>'
    });
    var btn = $('#briefToFeed');
    if (btn) btn.addEventListener('click', function () {
      closeModal();
      state.cat = 'all'; state.keyword = ''; state.query = '';
      $('#searchInput').value = '';
      renderCatChips(); renderFeed();
      scrollTo('#community');
    });
  }

  function openPast() {
    var past = (DATA.brief && DATA.brief.past) || [];
    if (!past.length) {
      openModal({
        eyebrow: 'ARCHIVE', title: '지난 호 보기',
        body: '<div class="empty-box">아직 지난 호가 없습니다.<br>매일 07:00 · 19:00 수집이 쌓이면 이 자리에 호별로 보관됩니다.</div>' +
          '<p class="micro-note">GitHub 에서는 <code>data/history/YYYY-MM-DD.json</code> 으로 보관하는 것을 권장합니다(설계서 참고).</p>',
        foot: '<button class="btn" type="button" data-close>닫기</button>'
      });
      return;
    }
    var rows = past.map(function (b, i) {
      return '<button class="issue-row" type="button" data-issue="' + i + '">' +
        '<span class="issue-no">' + esc(b.no || '') + '</span>' +
        '<span class="issue-t"><b>' + esc(b.title || '') + '</b><span>' + esc(b.date || '') + '</span></span></button>';
    }).join('');
    openModal({
      eyebrow: 'ARCHIVE', title: '지난 호 보기',
      body: rows, foot: '<button class="btn" type="button" data-close>닫기</button>'
    });
    $$('#modalBody .issue-row').forEach(function (row) {
      row.addEventListener('click', function () {
        var b = past[Number(row.getAttribute('data-issue'))];
        openModal({
          eyebrow: 'DAILY BRIEF · ' + (b.no || ''), title: b.title || '',
          body: briefBody(b),
          foot: '<button class="btn" type="button" id="backPast">← 목록</button>' +
                '<button class="btn" type="button" data-close>닫기</button>'
        });
        var back = $('#backPast'); if (back) back.addEventListener('click', openPast);
      });
    });
  }

  /* ---------------- 뉴스 ---------------- */
  function renderNews() {
    var news = DATA.news || [];
    var sections = ['전체'].concat(Array.from(new Set(news.map(function (n) { return n.section; }).filter(Boolean))));
    $('#newsTabs').innerHTML = sections.map(function (s) {
      return '<button class="chip" type="button" role="tab" data-news="' + esc(s) + '" ' +
        'aria-selected="' + (state.newsTab === s) + '">' + esc(s) + '</button>';
    }).join('');
    var list = news.filter(function (n) { return !n.noise && (state.newsTab === '전체' || n.section === state.newsTab); }).slice(0, 10);
    $('#newsList').innerHTML = list.length ? list.map(function (n) {
      return '<li><button class="news-item" type="button" data-news-id="' + esc(n.id) + '" data-testid="news-' + esc(n.id) + '">' +
        '<span class="news-src">' + esc((n.source || '').replace('구글뉴스 ', 'G뉴스 ')) + '</span>' +
        '<span class="news-title">' + esc(n.title) + '</span>' +
        '<span class="news-time">' + esc(n.time || '') + '</span></button></li>';
    }).join('') : '<li class="side-empty">수집된 뉴스가 없습니다</li>';
  }

  function openNewsAll() {
    var news = DATA.news || [];
    var body = news.map(function (n) {
      return '<div class="issue-row"><span class="badge-cat">' + esc(n.section || '') + '</span>' +
        '<span class="issue-t"><b>' + esc(n.title) + '</b><span>' + esc(n.source) + ' · ' + esc(n.time || '') + '</span></span>' +
        (n.url ? '<a class="btn btn-sm" href="' + esc(n.url) + '" target="_blank" rel="noopener">열기</a>' : '') + '</div>';
    }).join('');
    openModal({
      eyebrow: 'LIVE NEWS · ' + news.length + '건', title: '실시간 주요 뉴스',
      body: body || '<div class="empty-box">수집된 뉴스가 없습니다.</div>',
      foot: '<button class="btn" type="button" data-close>닫기</button>'
    });
  }

  /* ---------------- 유튜브 ---------------- */
  function renderYoutube() {
    var vids = DATA.videos || [];
    var mode = DATA.youtube_mode || 'channel-rss';
    $('#ytSub').textContent = mode === 'api'
      ? '실시간 인기 급상승(YouTube Data API) · 롱폼 · 쇼츠'
      : '채널 최신 업로드 · 인기 급상승은 YOUTUBE_API_KEY 연결 시';
    var list = vids.filter(function (v) { return state.ytTab === 'all' || (v.kind || 'long') === state.ytTab; });
    $('#ytList').innerHTML = list.length ? list.map(function (v, i) {
      var hue = hashHue(v.title || '');
      return '<a class="yt-item" href="' + esc(v.url || '#') + '" target="_blank" rel="noopener" data-testid="yt-' + i + '">' +
        '<span class="yt-thumb" style="--h:' + hue + '"><span>' + (v.kind === 'shorts' ? '🎬' : '▶️') + '</span>' +
        (v.rank ? '<span class="rk">' + v.rank + '</span>' : '') + '</span>' +
        '<span class="yt-body"><span class="yt-title">' + esc(v.title) + '</span>' +
        '<span class="yt-meta"><span class="yt-kind">' + (v.kind === 'shorts' ? '쇼츠' : '롱폼') + '</span>' +
        '<span>' + esc(v.channel || '') + '</span>' +
        (v.views ? '<span>· 조회 ' + compact(v.views) + '</span>' : '') +
        (v.time ? '<span>· ' + esc(v.time) + '</span>' : '') + '</span></span></a>';
    }).join('') : '<div class="empty"><b>수집된 영상이 없습니다</b>YouTube 채널 RSS 또는 API 키를 확인하세요.</div>';
  }

  /* ---------------- 블로그 ---------------- */
  function renderBlog() {
    var blogs = DATA.blogs || [];
    $('#blogGrid').innerHTML = blogs.length ? blogs.slice(0, 8).map(function (b, i) {
      var mark = (b.source || 'B').slice(0, 1);
      return '<a class="blog-item" href="' + esc(b.url || '#') + '" target="_blank" rel="noopener" data-testid="blog-' + i + '">' +
        '<span class="blog-mark" aria-hidden="true">' + esc(mark) + '</span>' +
        '<span class="blog-body"><span class="blog-title">' + esc(b.title) + '</span>' +
        '<span class="blog-meta">' + esc(b.source || '') + ' · ' + esc(b.time || '') + '</span></span></a>';
    }).join('') : '<div class="empty"><b>블로그 소재가 없습니다</b>네이버 블로그 키를 넣거나 RSS를 추가하세요.</div>';
  }

  /* ---------------- 핫딜 ---------------- */
  function renderDeals() {
    var deals = DATA.deals || [];
    $('#dealTrack').innerHTML = deals.map(function (d) {
      var on = !!findScrap(d.id);
      return '<article class="deal" data-id="' + esc(d.id) + '">' +
        '<div class="deal-top"><span class="deal-off">' + (d.off || 0) + '%</span>' +
        '<span class="deal-store">' + esc(d.store || '') + '</span></div>' +
        '<p class="deal-name">' + esc(d.name) + '</p>' +
        '<div class="deal-price"><b>' + won(d.price) + '</b><s>' + won(d.original) + '</s></div>' +
        '<p class="deal-note">' + esc(d.note || '') + (d.sample ? ' · 예시 가격' : '') + '</p>' +
        '<button class="act js-deal-scrap' + (on ? ' on' : '') + '" type="button" data-id="' + esc(d.id) + '" ' +
        'aria-pressed="' + on + '" data-testid="deal-scrap-' + esc(d.id) + '">' +
        '<span class="ico" aria-hidden="true">🎬</span>' + (on ? '스크랩됨' : '쿠팡 숏츠 소재로 스크랩') + '</button>' +
        '</article>';
    }).join('');
  }

  /* ---------------- 인디 ---------------- */
  var INDIE_TABS = [['all', '전체'], ['meta', '메타버스'], ['game', '웹 게임'], ['life', '생활·앱테크'], ['util', '웹 유틸']];

  function renderIndie() {
    var list = (DATA.indie || []).filter(function (p) { return state.indieTab === 'all' || p.tab === state.indieTab; });
    $('#indieTabs').innerHTML = INDIE_TABS.map(function (t) {
      return '<button class="chip" type="button" role="tab" data-indie="' + t[0] + '" ' +
        'aria-selected="' + (state.indieTab === t[0]) + '">' + t[1] + '</button>';
    }).join('');
    $('#indieGrid').innerHTML = list.length ? list.slice(0, 6).map(function (p) {
      return '<button class="indie" type="button" data-indie-id="' + esc(p.id) + '" data-testid="indie-' + esc(p.id) + '">' +
        '<span class="indie-top"><span class="indie-emoji" aria-hidden="true">' + esc(p.emoji || '🧩') + '</span>' +
        '<span class="indie-cat">' + esc(p.cat || '') + '</span></span>' +
        '<span class="indie-name">' + esc(p.name) + '</span>' +
        '<span class="indie-desc">' + esc(p.desc) + '</span>' +
        '<span class="indie-foot"><span>' + esc(p.maker || '') + '</span>' +
        (p.likes ? '<span>♥ ' + nfmt(p.likes) + '</span>' : '<span></span>') + '</span></button>';
    }).join('') : '<div class="empty"><b>해당 분류의 사례가 없습니다</b>다른 분류를 골라 보세요.</div>';
  }

  function openIndie(p) {
    openModal({
      eyebrow: 'INDIE PROJECT · ' + (p.cat || ''),
      title: (p.emoji || '🧩') + ' ' + p.name,
      body: '<p class="mb-p">' + esc(p.desc) + '</p>' +
        '<h3 class="mb-h">무엇이 불편했나</h3><p class="mb-p">' + esc((p.detail || {}).문제 || '-') + '</p>' +
        '<h3 class="mb-h">만든 기능</h3><p class="mb-p">' + esc((p.detail || {}).기능 || '-') + '</p>' +
        '<h3 class="mb-h">만든 방식</h3><p class="mb-p">' + esc((p.detail || {}).스택 || '-') + '</p>' +
        '<h3 class="mb-h">걸린 시간</h3><p class="mb-p">' + esc((p.detail || {}).시간 || '-') + '</p>',
      foot: (p.url ? '<a class="btn btn-amber" href="' + esc(p.url) + '" target="_blank" rel="noopener">사이트 열기</a>' : '') +
            '<span class="micro-note">' + esc(p.maker || '') + '</span><span class="spacer"></span>' +
            '<button class="btn" type="button" data-close>닫기</button>'
    });
  }

  /* ---------------- 오픈소스 · 앱 · 해커톤 · 벤치마크 ---------------- */
  function renderOpensource() {
    var list = DATA.opensource || [];
    $('#osList').innerHTML = list.length ? list.slice(0, 6).map(function (o, i) {
      return '<li><a class="os-item" href="' + esc(o.url || '#') + '" target="_blank" rel="noopener" data-testid="os-' + i + '">' +
        '<span class="os-ico" aria-hidden="true">🐙</span>' +
        '<span style="flex:1;min-width:0"><span class="os-repo">' + esc(o.repo) + '</span>' +
        '<span class="os-desc">' + esc(o.desc || '') + '</span></span>' +
        '<span class="os-stars">★ ' + compact(o.stars || 0) + '</span></a></li>';
    }).join('') : '<li class="side-empty">GitHub 트렌딩을 가져오지 못했습니다</li>';
  }

  function renderApps() {
    var apps = DATA.apps || [];
    var platforms = Array.from(new Set(apps.map(function (a) { return a.platform; })));
    if (!state.appTab || platforms.indexOf(state.appTab) < 0) state.appTab = platforms[0] || '';
    $('#appTabs').innerHTML = platforms.map(function (p) {
      return '<button class="chip" type="button" role="tab" data-app="' + esc(p) + '" ' +
        'aria-selected="' + (state.appTab === p) + '">' + esc(p) + '</button>';
    }).join('');
    var list = apps.filter(function (a) { return a.platform === state.appTab; });
    $('#appList').innerHTML = list.length ? list.map(function (a) {
      return '<li><button class="app-item" type="button" data-app-url="' + esc(a.url || '') + '">' +
        '<span class="app-rank">' + (a.rank || '') + '</span>' +
        '<span class="app-name">' + esc(a.name) + '</span>' +
        '<span class="app-cat">' + esc(a.category || '') + '</span></button></li>';
    }).join('') : '<li class="side-empty">순위를 가져오지 못했습니다</li>';
  }

  function renderHackathons() {
    var list = DATA.hackathons || [];
    $('#hackList').innerHTML = list.length ? list.slice(0, 6).map(function (h, i) {
      return '<li><a class="hack-item" href="' + esc(h.url || '#') + '" target="_blank" rel="noopener" data-testid="hack-' + i + '">' +
        '<span class="hack-dday">' + esc(h.dday || '모집중') + '</span>' +
        '<span class="hack-body"><span class="hack-name">' + esc(h.name) + '</span>' +
        '<span class="hack-meta">' + esc(h.host || '') + (h.deadline ? ' · ' + esc(h.deadline) : '') + (h.prize ? ' · ' + esc(h.prize) : '') + '</span></span>' +
        '</a></li>';
    }).join('') : '<li class="side-empty">공모전 정보를 가져오지 못했습니다</li>';
  }

  function renderBench() {
    var b = DATA.benchmarks || {};
    var rows = b.rows || [];
    var metric = state.benchTab;
    var factor = metric === '속도' ? 0.9 : metric === '가성비' ? 0.82 : 1;
    var adj = rows.map(function (r) {
      var v = Math.max(20, Math.round((r.score || 50) * factor + (metric === '지능' ? 0 : (r.rank % 3) * 4)));
      return { model: r.model, vendor: r.vendor, score: v, note: r.note };
    }).sort(function (a, b2) { return b2.score - a.score; });
    var max = Math.max.apply(null, adj.map(function (r) { return r.score; }).concat([1]));
    $('#benchList').innerHTML = adj.map(function (r, i) {
      return '<div class="bench-row"><span class="bench-name"><b>' + (i + 1) + '. ' + esc(r.model) + '</b>' +
        '<span>' + esc(r.vendor || '') + (r.note ? ' · ' + esc(r.note) : '') + '</span></span>' +
        '<span class="bench-bar"><i style="width:' + Math.round(r.score / max * 100) + '%"></i></span>' +
        '<span class="bench-score">' + r.score + '</span></div>';
    }).join('');
    $('#benchNote').textContent = (b.source || '수동 큐레이션') + ' · ' + metric + ' 지표는 참고용입니다.';
  }

  /* ---------------- 방문 추이 ---------------- */
  function renderChart() {
    var days = (DATA.visits && DATA.visits.days) || [];
    if (!days.length) { $('#chartBars').innerHTML = '<div class="side-empty">방문 기록이 없습니다</div>'; return; }
    var max = Math.max.apply(null, days.map(function (d) { return d.v; }));
    var min = Math.min.apply(null, days.map(function (d) { return d.v; }));
    var floor = Math.max(0, min - (max - min) * 0.4);
    var maxIdx = days.length - 1;   // 마지막 날 = 오늘
    $('#chartBars').innerHTML = days.map(function (d, i) {
      var h = Math.round(18 + (d.v - floor) / Math.max(1, (max - floor)) * 78);
      var prev = i > 0 ? days[i - 1].v : null;
      var diff = prev ? Math.round((d.v - prev) / prev * 1000) / 10 : null;
      var diffTxt = diff === null ? '첫날' : (diff >= 0 ? '▲ ' + diff + '%' : '▼ ' + Math.abs(diff) + '%');
      return '<div class="barwrap"><button class="bar' + (i === maxIdx ? ' is-today' : '') + '" type="button" ' +
        'style="height:' + h + '%" data-idx="' + i + '" data-testid="chart-bar-' + i + '" ' +
        'aria-label="' + d.d + '(' + d.wd + ') 방문 ' + nfmt(d.v) + '명">' +
        '<span class="bar-tip"><b>' + nfmt(d.v) + '명</b> ' + d.d + '(' + d.wd + ') · ' + diffTxt + '</span></button></div>';
    }).join('');
    $('#chartAxis').innerHTML = days.map(function (d, i) {
      return '<div' + (i === days.length - 1 ? ' class="today"' : '') + '><b>' + d.d + '</b>' + d.wd + '</div>';
    }).join('');
    var total = days.reduce(function (a, b) { return a + b.v; }, 0);
    $('#chartTotal').textContent = nfmt(total);
    var last = days[days.length - 1].v, prev = days.length > 1 ? days[days.length - 2].v : last;
    var trend = prev ? Math.round((last - prev) / prev * 1000) / 10 : 0;
    $('#chartTrend').textContent = (trend >= 0 ? '▲ ' + trend + '%' : '▼ ' + Math.abs(trend) + '%') + ' (전일 대비)';
    $('#chartSrc').textContent = (DATA.visits.source === 'sample') ? '샘플 추이' : '실측';
  }

  /* ---------------- 문의 및 제안 ---------------- */
  function renderInquiries() {
    $('#inqCount').textContent = inquiries.length;
    var list = $('#inqList');
    if (!inquiries.length) {
      list.innerHTML = '<div class="inq-empty">아직 남긴 제안이 없습니다.<br>오류·기능·소스 추가 요청을 남겨 주세요.</div>';
      return;
    }
    list.innerHTML = inquiries.map(function (q, i) {
      return '<div class="inq"><div class="inq-top"><span class="inq-type">' + esc(q.type) + '</span>' +
        '<span class="inq-time">' + esc((q.at || '').slice(5, 16).replace('T', ' ')) + '</span></div>' +
        '<div class="inq-title">' + esc(q.title || '(제목 없음)') + '</div>' +
        '<div class="inq-body">' + esc(q.body || '') + '</div>' +
        '<div class="inq-actions"><button class="icon-mini js-inq-copy" type="button" data-i="' + i + '" title="복사">📋</button>' +
        '<button class="icon-mini js-inq-del" type="button" data-i="' + i + '" title="삭제">🗑</button></div></div>';
    }).join('');
  }

  function inquiryMarkdown(q) {
    return '### [' + q.type + '] ' + (q.title || '(제목 없음)') + '\n\n' + (q.body || '') +
      '\n\n- 화면: 노리짱 트래픽센트 v2\n- 접수: ' + (q.at || '') + '\n- 데이터: ' + MODE;
  }

  function copyText(text, okMsg) {
    var done = function () {
      try { document.dispatchEvent(new CustomEvent('nori:copied', { detail: { text: text } })); } catch (e) {}
      toast(okMsg || '복사했습니다');
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(function () { fallbackCopy(text, done); });
    } else fallbackCopy(text, done);
  }
  function fallbackCopy(text, done) {
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); done(); } catch (e) { toast('복사에 실패했습니다'); }
    document.body.removeChild(ta);
  }

  function submitInquiry(e) {
    e.preventDefault();
    var type = $('#contactType').value;
    var title = $('#contactTitleInput').value.trim();
    var body = $('#contactBody').value.trim();
    if (!title && !body) { toast('제목이나 내용을 적어 주세요'); return; }
    var q = { id: 'q_' + Date.now(), type: type, title: title || '(제목 없음)', body: body,
              at: new Date().toISOString(), page: location.href.split('#')[0], mode: MODE };
    inquiries.unshift(q);
    saveJSON(LS_INQ, inquiries);
    renderInquiries();
    $('#contactTitleInput').value = ''; $('#contactBody').value = '';
    toast('제안을 저장했습니다 · 내 제안 기록에서 확인하세요');
  }

  function issueUrlFor(q) {
    var repo = (DATA.site && DATA.site.repo) || '';
    var md = inquiryMarkdown(q);
    if (!repo) return '';
    return 'https://github.com/' + repo + '/issues/new?title=' +
      encodeURIComponent('[' + q.type + '] ' + q.title) + '&body=' + encodeURIComponent(md) + '&labels=inquiry';
  }

  /* ---------------- 모달 ---------------- */
  var lastFocus = null;
  function openModal(opts) {
    lastFocus = document.activeElement;
    $('#modalEyebrow').textContent = opts.eyebrow || '';
    $('#modalTitle').textContent = opts.title || '';
    $('#modalBody').innerHTML = opts.body || '';
    $('#modalFoot').innerHTML = opts.foot || '';
    $('#modalRoot').hidden = false;
    document.body.style.overflow = 'hidden';
    var x = $('.modal-x'); if (x) x.focus({ preventScroll: true });
    $('#modalBody').scrollTop = 0;
  }
  function closeModal() {
    $('#modalRoot').hidden = true;
    document.body.style.overflow = '';
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus({ preventScroll: true }); } catch (e) {} }
  }

  function openFeedModal() {
    var list = currentFeed();
    var body = list.map(function (f) {
      return '<div class="issue-row"><span class="badge-cat">' + esc((CAT[f.cat] || {}).label || '') + '</span>' +
        '<span class="issue-t"><b>' + esc(f.title) + '</b><span>' + esc(f.source) + ' · ' + esc(f.time || '') + '</span></span>' +
        (f.url ? '<a class="btn btn-sm" href="' + esc(f.url) + '" target="_blank" rel="noopener">열기</a>' : '') + '</div>';
    }).join('');
    openModal({
      eyebrow: 'FEED · ' + list.length + '건', title: '통합 인기 피드 전체',
      body: body || '<div class="empty-box">표시할 항목이 없습니다.</div>',
      foot: '<button class="btn" type="button" data-close>닫기</button>'
    });
  }

  function openDetail(id) {
    var f = feedItem(id);
    if (!f) return;
    var m = CAT[f.cat] || CAT.comm;
    var on = !!findScrap(id);
    openModal({
      eyebrow: (m.label || '') + ' · ' + (f.source || ''),
      title: f.title,
      body: '<div class="detail-meta">' +
          '<span class="detail-src">' + esc(f.source) + '</span>' +
          '<span class="detail-src">' + esc(m.label) + '</span>' +
          (f.time ? '<span class="detail-src">' + esc(f.time) + '</span>' : '') +
          (f.sample ? '<span class="detail-src">예시 데이터</span>' : '') +
        '</div>' +
        (f.summary ? '<p class="mb-p">' + esc(f.summary) + '</p>' : '') +
        ((f.keywords || []).length ? '<p class="mb-p" style="color:var(--ink-3);font-size:12px">#' + f.keywords.map(esc).join(' #') + '</p>' : '') +
        '<p class="micro-note">' + (f.kind === 'news' ? '원문 기사는 아래 버튼으로 엽니다.' :
          f.kind === 'video' ? '유튜브에서 영상이 열립니다.' : '원문 게시글로 이동합니다.') + '</p>',
      foot: (f.url ? '<a class="btn btn-amber" href="' + esc(f.url) + '" target="_blank" rel="noopener">원문 열기</a>' : '') +
        '<button class="btn' + (on ? ' btn-dark' : '') + '" type="button" id="detailScrap">' + (on ? '★ 스크랩됨' : '⭐ 스크랩') + '</button>' +
        '<button class="btn" type="button" id="detailMemo">✍️ 글감 메모</button>' +
        '<span class="spacer"></span><button class="btn" type="button" data-close>닫기</button>'
    });
    var sb = $('#detailScrap');
    if (sb) sb.addEventListener('click', function () {
      toggleScrap(id); closeModal(); renderFeed();
    });
    var mb = $('#detailMemo');
    if (mb) mb.addEventListener('click', function () { openMemo(id); });
  }

  function openMemo(id) {
    var info = sourceInfo(id);
    var existing = findScrap(id);
    if (!info && !existing) return;
    var title = existing ? existing.title : info.title;
    openModal({
      eyebrow: 'IDEA NOTE', title: '✍️ 글감 메모',
      body: '<p class="mb-p" style="font-size:12.5px;color:var(--ink-3)">' + esc(title) + '</p>' +
        '<label class="sr-only" for="memoText">글감 메모</label>' +
        '<textarea id="memoText" class="memo-field" data-testid="memo-text" placeholder="예) 12월 숲놀이 모집글에 ‘겨울방학 4주 단기반’ 각도로. 우천 대체안 문단 먼저.">' +
        esc(existing ? existing.memo : '') + '</textarea>' +
        '<p class="memo-hint">저장하면 스크랩함에 함께 보관됩니다. 한 줄이면 충분해요.</p>',
      foot: '<button class="btn btn-amber" type="button" id="memoSave" data-testid="memo-save">메모 저장</button>' +
        '<span class="spacer"></span><button class="btn" type="button" data-close>취소</button>'
    });
    var ta = $('#memoText'); if (ta) ta.focus();
    $('#memoSave').addEventListener('click', function () {
      var v = ($('#memoText').value || '').trim();
      var s = findScrap(id);
      if (!s) {
        var inf = sourceInfo(id);
        if (!inf) return;
        s = { id: id, type: inf.type, title: inf.title, source: inf.source, meta: inf.meta, url: inf.url, memo: '', savedAt: new Date().toISOString() };
        scraps.unshift(s);
      }
      s.memo = v;
      saveJSON(LS_SCRAP, scraps);
      closeModal(); refreshScrap(); renderFeed(); renderDeals();
      toast(v ? '글감 메모를 저장했습니다' : '메모를 비웠습니다');
    });
  }

  function openScrapBox() {
    var body;
    if (!scraps.length) {
      body = '<div class="empty-box">아직 스크랩한 소재가 없습니다.<br>피드 카드의 ⭐, 핫딜의 🎬 버튼으로 모아 보세요.</div>';
    } else {
      body = scraps.map(function (s) {
        return '<div class="scrap-row" data-sid="' + esc(s.id) + '">' +
          '<div class="sr-body"><div class="sr-title">' + (s.type === 'deal' ? '🎬 ' : '⭐ ') + esc(s.title) + '</div>' +
          '<div class="sr-meta"><span class="badge-cat">' + (s.type === 'deal' ? '핫딜' : '인기글') + '</span>' +
          '<span>' + esc(s.source || '') + '</span>' + (s.meta ? '<span>' + esc(s.meta) + '</span>' : '') + '</div>' +
          (s.memo ? '<div class="sr-memo">' + esc(s.memo) + '</div>' : '') + '</div>' +
          '<div class="sr-actions">' +
          '<button class="icon-mini js-edit-memo" type="button" data-id="' + esc(s.id) + '" title="메모">✍️</button>' +
          '<button class="icon-mini js-del" type="button" data-id="' + esc(s.id) + '" title="삭제">🗑</button>' +
          '</div></div>';
      }).join('');
    }
    openModal({
      eyebrow: 'MY SCRAPBOX', title: '내 스크랩함 · ' + scraps.length + '건',
      body: body + '<p class="micro-note" style="margin-top:8px">이 브라우저(localStorage)에만 저장됩니다. 아래 JSON으로 백업·복원할 수 있어요.</p>',
      foot: '<button class="btn btn-amber" type="button" id="exportBtn">⬇ JSON 백업</button>' +
        '<button class="btn" type="button" id="importBtn">⬆ JSON 복원</button>' +
        '<span class="spacer"></span>' +
        '<button class="btn" type="button" id="clearBtn" style="color:#B91C1C">전체 삭제</button>' +
        '<button class="btn" type="button" data-close>닫기</button>'
    });
    var bodyEl = $('#modalBody');
    bodyEl.addEventListener('click', function (e) {
      var ed = e.target.closest('.js-edit-memo');
      if (ed) { openMemo(ed.getAttribute('data-id')); return; }
      var del = e.target.closest('.js-del');
      if (del) {
        var id = del.getAttribute('data-id'), i = -1;
        for (var k = 0; k < scraps.length; k++) if (scraps[k].id === id) { i = k; break; }
        if (i >= 0) {
          scraps.splice(i, 1); saveJSON(LS_SCRAP, scraps); refreshScrap(); renderFeed(); renderDeals();
          openScrapBox(); toast('스크랩을 삭제했습니다');
        }
      }
    }, { once: true });
    $('#exportBtn').addEventListener('click', exportJSON);
    $('#importBtn').addEventListener('click', function () { $('#importFile').click(); });
    $('#clearBtn').addEventListener('click', function () {
      if (scraps.length && window.confirm('스크랩 ' + scraps.length + '건을 모두 삭제할까요? 되돌릴 수 없습니다.')) {
        scraps = []; saveJSON(LS_SCRAP, scraps); refreshScrap(); renderFeed(); renderDeals();
        openScrapBox(); toast('모든 스크랩을 삭제했습니다');
      }
    });
  }

  function exportJSON() {
    try {
      var payload = { app: 'nori-traffic-scent', version: 2, exportedAt: new Date().toISOString(), items: scraps };
      var blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url; a.download = '노리짱_스크랩함_' + todayStamp() + '.json';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
      toast('JSON 파일로 내보냈습니다 (' + scraps.length + '건)');
    } catch (e) { toast('내보내기에 실패했습니다'); }
  }

  function openArch() {
    openModal({
      eyebrow: 'PIPELINE', title: '⚙️ 수집 · 요약 구조 (0원 구성)',
      body: '<p class="mb-p">하루 2번(07:00 / 19:00 KST) GitHub Actions가 돌아 공개 RSS·API를 모으고, ' +
        'Gemini Flash(무료 티어)로 요약해 <code>data.json</code> 한 파일로 커밋합니다. 화면은 그 JSON만 읽습니다.</p>' +
        '<div class="arch-flow">' +
        '<div class="arch-step"><span>1</span><div><b>수집 collector.py</b> — 일반 커뮤니티 9곳 · 뉴스 RSS · 유튜브 · 블로그 · 핫딜 · 오픈소스 · 앱·게임 · 해커톤. 키 없이도 공개 피드는 수집됩니다.</div></div>' +
        '<div class="arch-step"><span>2</span><div><b>정규화 · 중복 제거</b> — 제목 유사도 0.85 이상을 하나로 합치고 교차 출처 수를 셉니다.</div></div>' +
        '<div class="arch-step"><span>3</span><div><b>AI 요약 summarize.py</b> — Gemini Flash 배치 요약. 키가 없으면 규칙 기반 요약으로 자동 대체.</div></div>' +
        '<div class="arch-step"><span>4</span><div><b>data.json 자동 커밋</b> — GitHub Pages가 즉시 배포(서버비 0원).</div></div>' +
        '<div class="arch-step"><span>5</span><div><b>화면 fetch(\'./data.json\')</b> — 없으면 내장 데이터로 동작. 스크랩·메모·문의는 브라우저에 저장.</div></div>' +
        '</div>' +
        '<pre class="arch-code"><span class="c"># .github/workflows/collect.yml</span>\n' +
        '<span class="k">on</span>:\n  schedule:\n    - cron: \'0 22 * * *\'   <span class="c"># 07:00 KST</span>\n    - cron: \'0 10 * * *\'   <span class="c"># 19:00 KST</span>\n' +
        'jobs:\n  collect:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n' +
        '      - run: python collector.py\n      - run: python summarize.py\n' +
        '      - run: git commit -am "data: auto" &amp;&amp; git push</pre>' +
        '<h3 class="mb-h">비용</h3>' +
        '<table class="table-mini"><thead><tr><th>구성</th><th>월 비용</th><th>비고</th></tr></thead><tbody>' +
        '<tr><td>GitHub Actions + Pages</td><td>0원</td><td>공개 저장소 무료</td></tr>' +
        '<tr><td>Gemini Flash 무료 티어</td><td>0원</td><td>하루 2회 요약</td></tr>' +
        '<tr><td>네이버 검색 API</td><td>0원</td><td>일 25,000콜</td></tr>' +
        '<tr><td>YouTube Data API</td><td>0원</td><td>일 10,000 units</td></tr>' +
        '<tr><td>공공데이터포털</td><td>0원</td><td>나라장터·실거래가</td></tr>' +
        '</tbody></table>' +
        '<p class="micro-note">이 화면은 <b>' + (MODE === 'live' ? 'data.json 실데이터 연결 상태' : '내장 데이터(샘플) 상태') +
        '</b>입니다. GitHub에 올리면 주소 하나로 어디서나 열 수 있습니다.</p>',
      foot: '<button class="btn btn-dark" type="button" data-close>확인</button>' +
        '<span class="spacer"></span><span class="micro-note">서버비 0원 · 정적 호스팅</span>'
    });
  }

  function openMenu() {
    $('#menuSheet').hidden = false;
    $('#openMenu').setAttribute('aria-expanded', 'true');
    setTimeout(function () { var i = $('#menuSearch'); if (i) i.focus(); }, 40);
  }
  function closeMenu() {
    $('#menuSheet').hidden = true;
    $('#openMenu').setAttribute('aria-expanded', 'false');
  }

  function scrollTo(sel) {
    var el = $(sel);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* ---------------- 히어로 포털 · 통계 ---------------- */
  var PORTALS = [
    { key: 'brief', label: '리포트', bg: '#EFE9FE', fg: '#6D28D9',
      svg: '<path d="M7 4h7l4 4v12H7z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M10 10h6M10 13h6M10 16h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M13.5 4v4.5H18" fill="none" stroke="currentColor" stroke-width="1.6"/>' },
    { key: 'community', label: '커뮤니티', bg: '#FEF3C7', fg: '#B45309',
      svg: '<path d="M4 6h16v9H9l-5 4z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="9" cy="10.5" r="1" fill="currentColor"/><circle cx="12" cy="10.5" r="1" fill="currentColor"/><circle cx="15" cy="10.5" r="1" fill="currentColor"/>' },
    { key: 'news', label: '뉴스', bg: '#DBEAFE', fg: '#1D4ED8',
      svg: '<rect x="3.5" y="5" width="13" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="16.5" y="8" width="4" height="11" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M6.5 9h7M6.5 12h7M6.5 15h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' },
    { key: 'youtube', label: '유튜브', bg: '#FEE2E2', fg: '#DC2626',
      svg: '<rect x="3" y="6" width="18" height="12" rx="3.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M10.5 9.5l4.5 2.5-4.5 2.5z" fill="currentColor"/>' },
    { key: 'blog', label: '블로그', bg: '#E0F2FE', fg: '#0369A1',
      svg: '<path d="M5 5h10l4 4v10H5z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M8.5 10h7M8.5 13h7M8.5 16h4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' },
    { key: 'deal', label: '핫딜', bg: '#FFE4E6', fg: '#BE123C',
      svg: '<path d="M6 8h12l-1 11H7z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M9.5 8V6.5a2.5 2.5 0 015 0V8" fill="none" stroke="currentColor" stroke-width="1.8"/>' },
    { key: 'indie', label: '인디', bg: '#EDE9FE', fg: '#7C3AED',
      svg: '<path d="M12 3l7 4v9l-7 4-7-4V7z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M12 3v6M5 7l7 4 7-4" fill="none" stroke="currentColor" stroke-width="1.4" opacity=".6"/>' },
    { key: 'opensource', label: '오픈소스', bg: '#ECFDF5', fg: '#047857',
      svg: '<circle cx="7" cy="6.5" r="2.2" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="7" cy="17.5" r="2.2" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="17" cy="9" r="2.2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M7 8.7v6.6M17 11.2c0 3-3 3.4-5.5 3.6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' },
    { key: 'apps', label: '앱·게임', bg: '#E0F7FA', fg: '#0E7490',
      svg: '<rect x="3.5" y="4.5" width="7" height="7" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="13.5" y="4.5" width="7" height="7" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="3.5" y="14" width="7" height="6" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="13.5" y="14" width="7" height="6" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/>' },
    { key: 'hackathon', label: '해커톤', bg: '#FEF9C3', fg: '#A16207',
      svg: '<path d="M8 4h8v4a4 4 0 01-8 0z" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M8 6H5.5v1.5A2.5 2.5 0 008 10M16 6h2.5v1.5A2.5 2.5 0 0116 10" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M12 12v4M9 20h6M10 16h4l1 4H9z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>' },
    { key: 'benchmark', label: '벤치마크', bg: '#EDE9FE', fg: '#6D28D9',
      svg: '<path d="M12 3l1.9 4.3 4.6.5-3.5 3.2 1 4.6L12 13.4 8 15.6l1-4.6L5.5 7.8l4.6-.5z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M8 19h8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' },
    { key: 'contact', label: '문의하기', bg: '#DCFCE7', fg: '#15803D',
      svg: '<path d="M4 6h16v10H10l-6 4z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M8 10h8M8 13h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' }
  ];

  function renderPortals() {
    $('#portalGrid').innerHTML = PORTALS.map(function (p) {
      return '<button class="portal" type="button" data-goto="' + p.key + '" data-testid="portal-' + p.key + '" ' +
        'aria-label="' + p.label + ' 섹션으로 이동" style="color:' + p.fg + '">' +
        '<span class="portal-ico" style="background:' + p.bg + ';color:' + p.fg + '">' +
        '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">' + p.svg + '</svg></span>' +
        '<span class="portal-label" style="color:var(--ink-2)">' + p.label + '</span></button>';
    }).join('');
  }

  function renderStats() {
    var st = DATA.stats || {};
    var issue = DATA.issue || {};
    var gen = (DATA.generated_at || '').replace('T', ' ').slice(0, 16);
    var liveItems = FEED.filter(function (f) { return !f.sample; }).length;
    var hr = new Date().getHours();
    var nextRun = hr < 7 ? '07:00' : (hr < 19 ? '19:00' : '내일 07:00');
    var bits = [
      ['수집 출처', (st.live_sources || st.sources || 0) + '곳'],
      ['수집 글', (st.collected || FEED.length) + '건'],
      ['실데이터', liveItems + '건'],
      ['마지막 갱신', gen ? gen.slice(5, 16) : '-'],
      ['다음 수집', nextRun]
    ];
    $('#heroStats').innerHTML = bits.map(function (b) {
      return '<span class="hstat">' + b[0] + ' <b>' + esc(b[1]) + '</b></span>';
    }).join('');
  }

  function renderBadge() {
    var badge = $('#dataBadge');
    var narrow = window.innerWidth < 700;
    if (MODE === 'live') {
      badge.textContent = narrow ? 'LIVE' : '실데이터 연결됨';
      badge.className = 'pill pill-live';
      badge.title = 'data.json 을 읽었습니다 · 갱신 ' + (DATA.generated_at || '');
    } else {
      badge.textContent = narrow ? '샘플' : '샘플 데이터';
      badge.className = 'pill pill-amber';
      badge.title = '내장 스냅샷(' + (DATA.generated_at || '예시') + ')으로 동작 중입니다. http 서버 + data.json 이 있으면 실데이터로 전환됩니다.';
    }
  }

  /* ---------------- 이벤트 바인딩 ---------------- */
  function bind() {
    // 포털 · 섹션 이동
    $$('[data-goto]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var key = btn.getAttribute('data-goto');
        closeMenu();
        scrollTo('#' + key);
      });
    });

    // 카테고리 칩
    $('#catChips').addEventListener('click', function (e) {
      var b = e.target.closest('[data-cat]');
      if (!b) return;
      state.cat = b.getAttribute('data-cat');
      state.expanded = false;
      $$('#catChips .chip').forEach(function (t) { t.setAttribute('aria-selected', String(t === b)); });
      renderFeed();
    });

    // 피드 카드 액션 · 상세
    $('#feedGrid').addEventListener('click', function (e) {
      var sb = e.target.closest('.js-scrap');
      if (sb) { e.stopPropagation(); toggleScrap(sb.getAttribute('data-id')); return; }
      var mb = e.target.closest('.js-memo');
      if (mb) { e.stopPropagation(); openMemo(mb.getAttribute('data-id')); return; }
      var card = e.target.closest('.feed');
      if (card) openDetail(card.getAttribute('data-id'));
    });

    $('#moreBtn').addEventListener('click', function () {
      state.expanded = !state.expanded;
      renderFeed();
    });

    $('#openFeedAll').addEventListener('click', openFeedModal);

    // 정렬
    $('#sortHot').addEventListener('click', function () {
      state.sort = 'hot';
      $('#sortHot').setAttribute('aria-pressed', 'true');
      $('#sortRising').setAttribute('aria-pressed', 'false');
      renderFeed();
    });
    $('#sortRising').addEventListener('click', function () {
      state.sort = 'rising';
      $('#sortRising').setAttribute('aria-pressed', 'true');
      $('#sortHot').setAttribute('aria-pressed', 'false');
      renderFeed();
    });

    // 검색
    var si = $('#searchInput');
    si.addEventListener('input', function () {
      state.query = si.value; state.keyword = ''; state.expanded = false;
      $('#searchClear').hidden = !si.value;
      renderFeed();
    });
    $('#searchClear').addEventListener('click', function () {
      si.value = ''; state.query = ''; state.keyword = '';
      $('#searchClear').hidden = true;
      renderFeed(); si.focus();
    });
    $('#kwChipClear').addEventListener('click', function () {
      si.value = ''; state.query = ''; state.keyword = '';
      renderFeed();
    });
    $('#menuSearchGo').addEventListener('click', function () {
      var v = $('#menuSearch').value.trim();
      closeMenu(); si.value = v; state.query = v; state.keyword = '';
      $('#searchClear').hidden = !v;
      renderFeed(); scrollTo('#community');
    });
    $('#menuSearch').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); $('#menuSearchGo').click(); }
    });

    document.addEventListener('keydown', function (e) {
      var k = (e.key || '').toLowerCase();
      if ((e.metaKey || e.ctrlKey) && k === 'k') {
        e.preventDefault();
        if (!$('#modalRoot').hidden) closeModal();
        si.scrollIntoView({ block: 'center' });
        si.focus(); si.select();
        return;
      }
      if (e.key === 'Escape') {
        if (!$('#menuSheet').hidden) { closeMenu(); return; }
        if (!$('#modalRoot').hidden) { closeModal(); return; }
        if (document.activeElement === si && si.value) {
          si.value = ''; state.query = ''; $('#searchClear').hidden = true; renderFeed();
        }
      }
    });

    // 랭킹
    $('#rankTabs').addEventListener('click', function (e) {
      var b = e.target.closest('[data-rank]');
      if (!b) return;
      state.rankTab = b.getAttribute('data-rank');
      $$('#rankTabs .rtab').forEach(function (t) { t.setAttribute('aria-selected', String(t === b)); });
      renderRank();
    });
    function applyKeyword(kw) {
      state.keyword = kw; state.cat = 'all';
      si.value = kw; state.query = kw; state.expanded = false;
      $('#searchClear').hidden = false;
      $$('#catChips .chip').forEach(function (t) { t.setAttribute('aria-selected', String(t.getAttribute('data-cat') === 'all')); });
      renderFeed(); scrollTo('#community');
      toast('‘' + kw + '’ 관련 소재만 보고 있어요');
    }
    $('#rank').addEventListener('click', function (e) {
      var b = e.target.closest('[data-kw]');
      if (!b) return;
      applyKeyword(b.getAttribute('data-kw'));
    });

    // 브리프
    $('#openBrief').addEventListener('click', openBrief);
    $('#heroIssueBtn').addEventListener('click', openBrief);
    $('#openPast').addEventListener('click', openPast);

    // 뉴스
    $('#newsTabs').addEventListener('click', function (e) {
      var b = e.target.closest('[data-news]');
      if (!b) return;
      state.newsTab = b.getAttribute('data-news');
      renderNews();
    });
    $('#newsList').addEventListener('click', function (e) {
      var b = e.target.closest('[data-news-id]');
      if (b) openDetail(b.getAttribute('data-news-id'));
    });
    $('#openNewsAll').addEventListener('click', openNewsAll);

    // 유튜브
    $$('[data-yt]').forEach(function (b) {
      b.addEventListener('click', function () {
        state.ytTab = b.getAttribute('data-yt');
        $$('[data-yt]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        renderYoutube();
      });
    });

    // 핫딜
    $('#dealTrack').addEventListener('click', function (e) {
      var b = e.target.closest('.js-deal-scrap');
      if (!b) return;
      var on = toggleScrap(b.getAttribute('data-id'));
      renderDeals();
      if (on) toast('핫딜을 숏츠 소재로 스크랩했습니다');
    });
    function dealStep(dir) {
      var track = $('#dealTrack');
      var card = track.querySelector('.deal');
      var w = card ? card.getBoundingClientRect().width + 10 : 210;
      track.scrollBy({ left: dir * w * 2, behavior: 'smooth' });
    }
    $('#dealPrev').addEventListener('click', function () { dealStep(-1); });
    $('#dealNext').addEventListener('click', function () { dealStep(1); });

    // 인디
    $('#indieTabs').addEventListener('click', function (e) {
      var b = e.target.closest('[data-indie]');
      if (!b) return;
      state.indieTab = b.getAttribute('data-indie');
      renderIndie();
    });
    $('#indieGrid').addEventListener('click', function (e) {
      var b = e.target.closest('[data-indie-id]');
      if (!b) return;
      var p = (DATA.indie || []).filter(function (x) { return x.id === b.getAttribute('data-indie-id'); })[0];
      if (p) openIndie(p);
    });
    $('#openIndieAll').addEventListener('click', function () {
      state.indieTab = 'all'; renderIndie();
      openModal({
        eyebrow: 'INDIE PROJECTS', title: '인디 프로젝트 전체',
        body: (DATA.indie || []).map(function (p) {
          return '<div class="issue-row"><span class="badge-cat">' + esc(p.cat || '') + '</span>' +
            '<span class="issue-t"><b>' + esc((p.emoji || '') + ' ' + p.name) + '</b><span>' + esc(p.desc || '') + '</span></span></div>';
        }).join(''),
        foot: '<button class="btn" type="button" data-close>닫기</button>'
      });
    });

    // 앱 탭
    $('#appTabs').addEventListener('click', function (e) {
      var b = e.target.closest('[data-app]');
      if (!b) return;
      state.appTab = b.getAttribute('data-app');
      renderApps();
    });
    $('#appList').addEventListener('click', function (e) {
      var b = e.target.closest('[data-app-url]');
      if (!b) return;
      var url = b.getAttribute('data-app-url');
      if (url) window.open(url, '_blank', 'noopener');
    });

    // 벤치마크 탭
    $('#benchTabs').addEventListener('click', function (e) {
      var b = e.target.closest('[data-bench]');
      if (!b) return;
      state.benchTab = b.getAttribute('data-bench');
      $$('#benchTabs button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      renderBench();
    });

    // 차트
    $('#chartBars').addEventListener('click', function (e) {
      var b = e.target.closest('.bar');
      if (!b) return;
      var was = b.classList.contains('is-on');
      $$('#chartBars .bar').forEach(function (x) { x.classList.remove('is-on'); });
      if (!was) b.classList.add('is-on');
    });

    // 문의
    $('#contactForm').addEventListener('submit', submitInquiry);
    function currentDraft() {
      var title = $('#contactTitleInput').value.trim();
      var body = $('#contactBody').value.trim();
      if (title || body) {
        return { type: $('#contactType').value, title: title || '(제목 없음)', body: body,
                 at: new Date().toISOString() };
      }
      return inquiries[0] || null;   // 입력창이 비어 있으면 마지막으로 저장한 제안을 사용
    }
    $('#contactCopy').addEventListener('click', function () {
      var draft = currentDraft();
      if (!draft) { toast('내용을 먼저 적어 주세요'); return; }
      copyText(inquiryMarkdown(draft), '문의 내용을 복사했습니다 · 메일이나 메시지에 붙여 넣으세요');
    });
    $('#contactIssue').addEventListener('click', function () {
      var q = currentDraft();
      if (!q) { toast('내용을 먼저 적어 주세요'); return; }
      var url = issueUrlFor(q);
      if (url) { window.open(url, '_blank', 'noopener'); return; }
      copyText(inquiryMarkdown(q), '저장소 주소가 아직 없어 내용을 복사했습니다 · GitHub Issues에 붙여 넣으세요');
    });
    $('#inqList').addEventListener('click', function (e) {
      var c = e.target.closest('.js-inq-copy');
      if (c) { copyText(inquiryMarkdown(inquiries[Number(c.getAttribute('data-i'))])); return; }
      var d = e.target.closest('.js-inq-del');
      if (d) {
        inquiries.splice(Number(d.getAttribute('data-i')), 1);
        saveJSON(LS_INQ, inquiries); renderInquiries(); toast('제안 기록을 삭제했습니다');
      }
    });

    // 스크랩 · 구조 · 메뉴
    $('#openScrapTop').addEventListener('click', openScrapBox);
    $('#openScrapBox').addEventListener('click', openScrapBox);
    $('#menuScrap').addEventListener('click', function () { closeMenu(); openScrapBox(); });
    $('#exportTop').addEventListener('click', exportJSON);
    $('#menuExport').addEventListener('click', exportJSON);
    $('#menuImport').addEventListener('click', function () { $('#importFile').click(); });
    $('#openArchTop').addEventListener('click', openArch);
    $('#openArch2').addEventListener('click', openArch);
    $('#menuArch').addEventListener('click', function () { closeMenu(); openArch(); });
    $('#footArch').addEventListener('click', openArch);
    $('#openMenu').addEventListener('click', function () {
      if ($('#menuSheet').hidden) openMenu(); else closeMenu();
    });
    document.addEventListener('click', function (e) {
      if (e.target.closest('[data-menu-close]')) closeMenu();
    });

    // JSON 복원
    $('#importFile').addEventListener('change', function (e) {
      var file = e.target.files && e.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        try {
          var data = JSON.parse(String(reader.result));
          var items = Array.isArray(data) ? data : (data && data.items);
          if (!Array.isArray(items)) throw new Error('format');
          var added = 0, updated = 0;
          items.forEach(function (it) {
            if (!it || !it.id || !it.title) return;
            var cur = findScrap(it.id);
            if (cur) { cur.memo = it.memo || cur.memo; updated++; }
            else {
              scraps.push({ id: it.id, type: it.type || 'post', title: it.title, source: it.source || '',
                            meta: it.meta || '', url: it.url || '', memo: it.memo || '',
                            savedAt: it.savedAt || new Date().toISOString() });
              added++;
            }
          });
          saveJSON(LS_SCRAP, scraps); refreshScrap(); renderFeed(); renderDeals();
          toast('불러왔습니다 · 새로 ' + added + '건, 갱신 ' + updated + '건');
          if (!$('#modalRoot').hidden) openScrapBox();
        } catch (err) { toast('JSON 형식이 맞지 않습니다'); }
      };
      reader.readAsText(file);
      e.target.value = '';
    });

    // 모달 공통
    $('#modalRoot').addEventListener('click', function (e) {
      if (e.target.closest('[data-close]')) closeModal();
    });

    // 언어 pill (표시용)
    $('#langPill').addEventListener('click', function () {
      toast('한국어(KO) · Asia/Seoul 기준으로 표시합니다');
    });
    // 좁은 화면 검색 버튼 → 메뉴 시트의 검색으로
    var narrowSearch = $('#openSearchBtn');
    if (narrowSearch) narrowSearch.addEventListener('click', function () { openMenu(); });
  }

  /* ---------------- 렌더 총괄 ---------------- */
  function renderAll() {
    renderPortals();
    renderStats();
    renderBadge();
    renderCatChips();
    renderFeed();
    renderRankTabs();
    renderRank();
    renderBrief();
    renderNews();
    renderYoutube();
    renderBlog();
    renderDeals();
    renderIndie();
    renderOpensource();
    renderApps();
    renderHackathons();
    renderBench();
    renderChart();
    renderInquiries();
    refreshScrap();
  }

  /* ---------------- 부팅 ---------------- */
  async function boot() {
    if (/^https?:/.test(location.protocol)) {
      try {
        var res = await fetch('./data.json', { cache: 'no-store' });
        if (res.ok) {
          var json = await res.json();
          if (json && Array.isArray(json.posts)) {
            DATA = Object.assign({}, EMBEDDED, json);
            FEED = normalizeFeed();
            MODE = 'live';
          }
        }
      } catch (e) { /* data.json 없음 → 내장 데이터 */ }
    }
    renderAll();
    bind();
    var rt = null;
    window.addEventListener('resize', function () {
      clearTimeout(rt);
      rt = setTimeout(renderBadge, 180);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
