/* =========================================================================
   트렌드픽 TrendPick v3 · app.js
   데이터 렌더 · 필터 · 검색 · 저장한 픽(localStorage) · 광고 슬롯 · 모달
   외부 라이브러리 0개
   ========================================================================= */
(function () {
  'use strict';

  /* ------------------------------------------------------------------
     광고 설정 — 여기만 채우면 바로 노출됩니다.
     · 애드센스: client(예: ca-pub-0000000000000000)와 슬롯 4개(data-ad-slot)
     · 카카오 애드핏: unit(예: DAN-xxxxxx)과 광고 영역 크기
     · 둘 다 비어 있으면 광고 상자는 화면에서 완전히 숨겨집니다.
       (푸터 [📢 광고 자리 미리보기] 또는 ?ad_preview=1 로 위치·비율만 확인)
  ------------------------------------------------------------------ */
  var TRENDPICK_ADS = {
    enabled: true,
    adsense: {
      client: '',                 // ca-pub-...
      slots: { top: '', feed: '', side: '', bottom: '' }   // data-ad-slot 값
    },
    kakao: {
      unit: '',                   // DAN-...
      width: '320',
      height: '100'
    },
    preview: false                // true 면 광고 ID 없이도 자리 미리보기
  };

  /* ------------------------------ 유틸 ------------------------------ */
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
  function hashHue(str) {
    var h = 0;
    for (var i = 0; i < (str || '').length; i++) h = (h * 31 + str.charCodeAt(i)) % 360;
    return h;
  }
  var toastTimer = null;
  function toast(msg) {
    var t = $('#toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove('show'); }, 2300);
  }

  /* ------------------------------ 데이터 ------------------------------ */
  var EMBEDDED = {
    posts: [], news: [], videos: [], blogs: [], deals: [], opensource: [], apps: [], hackathons: [],
    ranks: { all: [] }, brief: { sections: [], picks: [] }, stats: {}, issue: {}, thumbs: {}
  };
  try {
    EMBEDDED = Object.assign(EMBEDDED, JSON.parse($('#embeddedData').textContent || '{}'));
  } catch (e) { /* 내장 데이터가 깨져도 화면은 계속 */ }

  var DATA = EMBEDDED;
  var MODE = 'snapshot';

  var CAT = {
    all:      { label: '전체' },
    comm:     { label: '커뮤니티' },
    news:     { label: '뉴스' },
    youtube:  { label: '유튜브' },
    web:      { label: '블로그' },
    mom:      { label: '맘카페·육아' },
    estate:   { label: '부동산·경매' },
    ai:       { label: 'AI·부업' },
    apptech:  { label: '앱테크·핫딜' },
    build:    { label: '건축·입찰' },
    apps:     { label: '앱·게임' },
    os:       { label: '오픈소스' },
    hack:     { label: '해커톤' },
    deal:     { label: '핫딜' }
  };
  var TOPIC_ORDER = ['mom', 'estate', 'ai', 'apptech', 'build'];

  var state = {
    filter: 'all', sort: 'hot', q: '', kw: '', savedOnly: false,
    limit: 12, newsSec: '전체', appTab: '', bench: null
  };

  /* --------------------------- 저장한 픽 --------------------------- */
  var LS_SAVED = 'trendpick:saved:v1';
  function loadSaved() {
    try {
      var raw = localStorage.getItem(LS_SAVED);
      var arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }
  function persistSaved() {
    try { localStorage.setItem(LS_SAVED, JSON.stringify(saved)); return true; }
    catch (e) { toast('저장 공간을 쓸 수 없어 이번 화면에서만 유지됩니다'); return false; }
  }
  var saved = loadSaved();

  function savedIndex(id) {
    for (var i = 0; i < saved.length; i++) if (saved[i].id === id) return i;
    return -1;
  }
  function isSaved(id) { return savedIndex(id) >= 0; }

  function itemById(id) {
    for (var i = 0; i < FEED.length; i++) if (FEED[i].id === id) return FEED[i];
    return null;
  }
  function toggleSaved(id) {
    var i = savedIndex(id);
    if (i >= 0) {
      saved.splice(i, 1);
      persistSaved(); refreshSaved();
      renderFeed();
      toast('저장을 해제했습니다');
      return false;
    }
    var it = itemById(id);
    if (!it) return false;
    saved.unshift({
      id: it.id, title: it.title, source: it.source, url: it.url, img: it.img || '',
      cat: it.cat, at: new Date().toISOString()
    });
    persistSaved(); refreshSaved();
    renderFeed();
    toast('저장했습니다 · 오른쪽 ⭐ 저장한 픽에서 다시 볼 수 있어요');
    return true;
  }
  function refreshSaved() {
    var n = saved.length;
    ['#savedN', '#savedN2'].forEach(function (sel) { var el = $(sel); if (el) el.textContent = n; });
    var mini = $('#savedMini');
    if (mini) {
      if (!n) {
        mini.innerHTML = '<p class="saved-empty">아직 저장한 픽이 없습니다.<br>카드 오른쪽 ★ 를 누르면 여기에 모입니다.</p>';
      } else {
        mini.innerHTML = saved.slice(0, 4).map(function (s) {
          return '<a class="saved-item" href="' + esc(s.url || '#') + '" target="_blank" rel="noopener">' +
            '<span><span class="si-t">' + esc(s.title) + '</span>' +
            '<span class="si-s">' + esc(s.source || '') + '</span></span></a>';
        }).join('') + (n > 4 ? '<p class="micro-note">외 ' + (n - 4) + '건 더 저장됨</p>' : '');
      }
    }
    var chip = $('#savedChip');
    if (chip) chip.hidden = !state.savedOnly;
    var btn = $('#savedBtn');
    if (btn) btn.setAttribute('aria-pressed', String(state.savedOnly));
  }

  /* ------------------------ 카테고리별 일러스트 ------------------------ */
  var ART = {
    comm:    { bg: '#EDF2F4', fg: '#334155', g: 'M4 6.5h16v9.5h-8.5L6 20v-4H4z M8 11h8 M8 14h5' },
    news:    { bg: '#EEF3FB', fg: '#1E3A8A', g: 'M4 5h12v14H4z M16 8h4v9a2 2 0 0 1-2 2h-2 M7 9h6 M7 12h6 M7 15h4' },
    youtube: { bg: '#FFF0F3', fg: '#BE123C', g: 'M3.5 8.5A2.5 2.5 0 0 1 6 6h12a2.5 2.5 0 0 1 2.5 2.5v7A2.5 2.5 0 0 1 18 18H6a2.5 2.5 0 0 1-2.5-2.5z M10.5 9.6l4.6 2.4-4.6 2.4z' },
    web:     { bg: '#EFF6FF', fg: '#1D4ED8', g: 'M5 4.5h8.5L19 10v9.5H5z M13 4.5V10h5.5 M8 13h8 M8 16h5' },
    mom:     { bg: '#EAF7F0', fg: '#047857', g: 'M12 20c5-3 7-6.2 7-9a7 7 0 0 0-14 0c0 2.8 2 6 7 9z M12 11.5v-5 M12 8c-2 0-3.2-1-3.6-2.4' },
    estate:  { bg: '#F3F1FA', fg: '#5B21B6', g: 'M4 20V9l8-4.5L20 9v11 M9 20v-6h6v6 M7.5 11.5h2 M14.5 11.5h2' },
    ai:      { bg: '#EAF8F5', fg: '#0F766E', g: 'M8 8h8v8H8z M12 4.5v3.5 M12 16v3.5 M4.5 12H8 M16 12h3.5 M8 8 5.5 5.5 M16 8l2.5-2.5 M8 16l-2.5 2.5 M16 16l2.5 2.5' },
    apptech: { bg: '#FFF6EC', fg: '#B45309', g: 'M7 8.5h10l-1 11.5H8z M9.8 8.5V7a2.2 2.2 0 0 1 4.4 0v1.5 M10.5 13h3' },
    build:   { bg: '#FEFBEB', fg: '#A16207', g: 'M4 17.5h16 M6.5 17.5V9l5.5-3.5L17.5 9v8.5 M9 17.5v-4h6v4 M12 2.5v3' },
    apps:    { bg: '#EEF1FE', fg: '#4338CA', g: 'M4.5 5.5h6v6h-6z M13.5 5.5h6v6h-6z M4.5 13.5h6v5h-6z M13.5 13.5h6v5h-6z' },
    os:      { bg: '#F2F3F5', fg: '#111827', g: 'M7.5 6.5a2 2 0 1 1-4 0 2 2 0 0 1 4 0z M7.5 17.5a2 2 0 1 1-4 0 2 2 0 0 1 4 0z M19.5 9a2 2 0 1 1-4 0 2 2 0 0 1 4 0z M7.5 8.5v7 M15.5 11c-1.5 3.5-4 4-7 4' },
    hack:    { bg: '#FEF1F1', fg: '#B91C1C', g: 'M8 4.5h8v4a4 4 0 0 1-8 0z M8 6.5H5.5v1.2A2.8 2.8 0 0 0 8.3 10.5 M16 6.5h2.5v1.2a2.8 2.8 0 0 1-2.8 2.8 M12 12.5v4 M9 20h6 M10 16.5h4l1 3.5H9z' },
    deal:    { bg: '#FFF0F3', fg: '#9F1239', g: 'M12.5 3.5H20v7.5l-8.5 8.5L4 12z M16.5 7.5h.01' }
  };

  function artSvg(cat) {
    var a = ART[cat] || ART.news;
    var lines = '';
    for (var i = 1; i < 7; i++) lines += '<line x1="' + (i * 46) + '" y1="0" x2="' + (i * 46) + '" y2="180"/>';
    for (var j = 1; j < 4; j++) lines += '<line x1="0" y1="' + (j * 45) + '" x2="320" y2="' + (j * 45) + '"/>';
    var label = (CAT[cat] && CAT[cat].label) || '트렌드';
    return '<span class="art" aria-hidden="true"><svg viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice">' +
      '<rect width="320" height="180" fill="' + a.bg + '"/>' +
      '<g stroke="' + a.fg + '" stroke-opacity=".07" stroke-width="1">' + lines + '</g>' +
      '<circle cx="268" cy="34" r="64" fill="' + a.fg + '" opacity=".05"/>' +
      '<circle cx="268" cy="34" r="34" fill="none" stroke="' + a.fg + '" stroke-opacity=".16" stroke-width="1.2"/>' +
      '<circle cx="268" cy="34" r="6" fill="' + a.fg + '" opacity=".22"/>' +
      '<g transform="translate(112,38) scale(3.6)" fill="none" stroke="' + a.fg + '" stroke-width="1.25" ' +
        'stroke-linecap="round" stroke-linejoin="round" opacity=".66"><path d="' + a.g + '"/></g>' +
      '<text x="16" y="152" font-family="ui-monospace,SFMono-Regular,monospace" font-size="9.5" ' +
        'letter-spacing="2.6" fill="' + a.fg + '" opacity=".4">TRENDPICK</text>' +
      '<text x="16" y="168" font-size="12" font-weight="700" letter-spacing=".4" fill="' + a.fg + '" ' +
        'opacity=".5">' + esc(label) + '</text></svg></span>';
  }

  /* --------------------------- 통합 피드 --------------------------- */
  var FEED = [];
  function normalize() {
    var feed = [];
    (DATA.posts || []).forEach(function (p) {
      feed.push(mkItem(p, p.cat || 'comm', 'post'));
    });
    (DATA.news || []).forEach(function (n) {
      if (n.noise) return;
      feed.push(mkItem(n, 'news', 'news'));
    });
    (DATA.videos || []).forEach(function (v) {
      feed.push(mkItem(v, 'youtube', v.kind === 'shorts' ? 'shorts' : 'video'));
    });
    (DATA.blogs || []).forEach(function (b) {
      feed.push(mkItem(b, 'web', 'blog'));
    });
    return feed;
  }
  function mkItem(o, cat, kind) {
    var topics = o.topics || [];
    var cats = [cat].concat(topics.filter(function (t) { return t !== cat; }));
    return {
      id: o.id || ('x_' + hashHue(o.title || '')),
      cat: cat, cats: cats, kind: kind,
      source: o.source || o.channel || '', title: o.title || '',
      url: o.url || '', img: o.img || '',
      time: o.time || '', published: o.published || '',
      hot: o.hot || 50, rise: o.rise || 100,
      views: o.views || 0,
      section: o.section || '',
      hue: hashHue(o.title || '')
    };
  }
  FEED = normalize();

  /* --------------------------- 광고 --------------------------- */
  var adPreview = !!TRENDPICK_ADS.preview ||
    /[?&]ad_preview=1/.test(location.search);
  var adScriptLoaded = false;

  function adsenseReady(key) {
    var c = TRENDPICK_ADS.adsense || {};
    return !!(TRENDPICK_ADS.enabled && c.client && c.slots && c.slots[key]);
  }
  function kakaoReady() {
    var k = TRENDPICK_ADS.kakao || {};
    return !!(TRENDPICK_ADS.enabled && k.unit);
  }
  function anyAdReady() { return adsenseReady('top') || adsenseReady('side') || kakaoReady(); }

  function loadAdScripts() {
    if (adScriptLoaded) return;
    adScriptLoaded = true;
    var c = TRENDPICK_ADS.adsense || {};
    if (c.client) {
      var s = document.createElement('script');
      s.async = true;
      s.crossOrigin = 'anonymous';
      s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + encodeURIComponent(c.client);
      document.head.appendChild(s);
    }
    if (kakaoReady()) {
      var k = document.createElement('script');
      k.async = true;
      k.src = 'https://t1.daumcdn.net/kas/static/ba.min.js';
      document.head.appendChild(k);
    }
  }

  function adLabel(key) {
    return '<div class="ad-label">AD · ' + esc(key === 'side' ? '사이드바 300 × 250'
      : key === 'feed' ? '피드 인라인' : '배너 728 × 90 / 320 × 100') + '</div>';
  }
  function adPreviewBox(key, size) {
    return adLabel(key) +
      '<div class="ad-box"><b>광고 자리 미리보기</b>' +
      '<span>' + esc(size) + '</span>' +
      '<span>TRENDPICK_ADS 에 ID를 넣으면 이 자리에 광고가 나옵니다</span></div>';
  }

  function adInner(key, size) {
    if (adsenseReady(key)) {
      var c = TRENDPICK_ADS.adsense;
      return adLabel(key) +
        '<ins class="adsbygoogle" style="display:block" data-ad-client="' + esc(c.client) +
        '" data-ad-slot="' + esc(c.slots[key]) + '" data-ad-format="auto" data-full-width-responsive="true"></ins>';
    }
    if (kakaoReady() && key !== 'feed') {
      var k = TRENDPICK_ADS.kakao;
      return adLabel(key) +
        '<ins class="kakao_ad_area" style="display:none" data-ad-unit="' + esc(k.unit) +
        '" data-ad-width="' + esc(k.width) + '" data-ad-height="' + esc(k.height) + '"></ins>';
    }
    if (adPreview) return adPreviewBox(key, size || '');
    return '';
  }

  function renderAds() {
    var any = anyAdReady();
    if (any) loadAdScripts();
    $$('.ad-slot').forEach(function (el) {
      var key = el.getAttribute('data-ad');
      var size = el.getAttribute('data-size') || '';
      var html = adInner(key, size);
      el.innerHTML = html;
      el.classList.toggle('on', !!html);
    });
    if (any && window.adsbygoogle) {
      $$('.ad-slot ins.adsbygoogle').forEach(function (ins) {
        if (ins.getAttribute('data-adsbygoogle-status')) return;
        try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) {}
      });
    }
    var pv = $('#adPreviewBtn');
    if (pv) {
      pv.textContent = adPreview ? '📢 광고 자리 미리보기 끄기' : '📢 광고 자리 미리보기';
      pv.style.color = adPreview ? 'var(--coral)' : '';
    }
  }

  /* --------------------------- 브리프 --------------------------- */
  function renderBrief() {
    var b = DATA.brief || {};
    var issue = DATA.issue || {};
    var st = DATA.stats || {};
    var gen = (DATA.generated_at || '').replace('T', ' ').slice(0, 16);
    $('#bNo').textContent = b.no || ('No.' + String(issue.no || 1).padStart(2, '0'));
    $('#bDate').textContent = (b.label || '') + (b.weekday ? ' ' + b.weekday : '');
    $('#bEyebrow').textContent = '오늘의 트렌드픽 브리프 · ' + (b.date || issue.date || '');
    $('#bTitle').textContent = (b.picks && b.picks[0] && b.picks[0].title) || b.title || '오늘의 트렌드픽 브리프';
    $('#bLead').textContent = b.lead || '';

    var picks = b.picks || [];
    var lead = picks[0] || { title: b.title || '', url: '', img: '', label: '', source: '' };
    $('#bTitle').textContent = lead.title || b.title || '오늘의 트렌드픽 브리프';
    $('#bLead').textContent = b.lead || '';

    // 헤드라인은 대표 기사, 그 아래 핫픽 3선(서로 다른 분야 우선)
    var hotPicks = picks.slice(1, 4);
    var pickCat = function (label) {
      return label === 'IT·AI' ? 'ai' : label === '부동산·정책' ? 'estate' : 'news';
    };
    $('#bPicks').innerHTML = hotPicks.map(function (p, i) {
      return '<li><a class="pick-row" href="' + esc(p.url || '#') + '" target="_blank" rel="noopener" data-testid="brief-pick-' + i + '">' +
        '<span class="pick-no">' + String(i + 1).padStart(2, '0') + '</span>' +
        '<span class="pick-thumb">' + artSvg(pickCat(p.label)) +
          (p.img ? '<img src="' + esc(p.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
        '</span>' +
        '<span><span class="pick-t">' + esc(p.title) + '</span>' +
        '<span class="pick-src">' + esc(p.label || '') + ' · ' + esc(p.source || '') + '</span></span></a></li>';
    }).join('');

    if (lead.url) {
      $('#bTitle').style.cursor = 'pointer';
      $('#bTitle').onclick = function () { window.open(lead.url, '_blank', 'noopener'); };
    }

    var bits = [];
    if (st.live_sources || st.sources) bits.push('수집 출처 ' + (st.live_sources || st.sources) + '곳');
    var items = (b.metrics && b.metrics.items) || st.collected;
    if (items) bits.push('수집 ' + items + '건');
    if (gen) bits.push(gen + ' 갱신');
    $('#bMeta').textContent = bits.join(' · ');
  }

  function briefModal() {
    var b = DATA.brief || {};
    var secs = (b.sections || []).map(function (s) {
      var points = (s.points || []).map(function (p) {
        var text = typeof p === 'string' ? p : p.text;
        var url = typeof p === 'string' ? '' : p.url;
        return '<li>' + (url
          ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(text) + '</a>'
          : esc(text)) + '</li>';
      }).join('');
      return '<div class="brief-sec"><h3><span>' + esc(s.label || '') + '</span>' + esc(s.title || '') + '</h3>' +
        '<p>' + esc(s.body || '') + '</p>' +
        (points ? '<ul>' + points + '</ul>' : '') + '</div>';
    }).join('');
    openModal({
      eyebrow: 'DAILY BRIEF · ' + (b.no || '') + ' · ' + (b.date || ''),
      title: '오늘의 트렌드픽 브리프',
      body: '<p class="mb-p">' + esc(b.lead || '') + '</p>' + (secs || '<p class="mb-p">수집된 이슈가 없습니다.</p>') +
        '<p class="micro-note" style="margin-top:14px">※ 공개 RSS·API 로 수집한 제목을 규칙 기반으로 묶었습니다. 원문은 각 항목의 링크에서 확인하세요. ' +
        (b.engine && b.engine.indexOf('gemini') === 0 ? '문장 요약: Gemini Flash.' : '') + '</p>',
      foot: '<button class="btn btn-ink" type="button" id="toFeed">이 키워드로 피드 보기</button>' +
        '<button class="btn btn-line" type="button" data-close>닫기</button>' +
        '<span style="flex:1"></span><span class="micro">' + esc((b.metrics && b.metrics.topics ? b.metrics.topics + '개 분야 · ' : '') +
        ((b.metrics && b.metrics.items) || 0) + '건 수집') + '</span>'
    });
    var btn = $('#toFeed');
    if (btn) btn.addEventListener('click', function () {
      closeModal();
      state.filter = 'all'; state.q = ''; state.kw = '';
      $('#q').value = '';
      renderChips(); renderFeed();
      document.getElementById('explore').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  function pastModal() {
    var past = (DATA.brief && DATA.brief.past) || [];
    if (!past.length) {
      openModal({
        eyebrow: 'ARCHIVE', title: '지난 호',
        body: '<p class="mb-p">아직 지난 호가 없습니다. 매일 수집이 쌓이면 이 자리에 호별로 보관됩니다.</p>' +
          '<p class="micro-note">GitHub 저장소의 <code>data/history/YYYY-MM-DD.json</code> 에 하루 단위로 남습니다.</p>',
        foot: '<button class="btn" type="button" data-close>닫기</button>'
      });
      return;
    }
    openModal({
      eyebrow: 'ARCHIVE · ' + past.length + '호', title: '지난 호 보기',
      body: '<div class="saved-mini">' + past.map(function (p, i) {
        return '<button class="issue-row" type="button" data-past="' + i + '">' +
          '<span class="issue-no">' + esc(p.no || '') + '</span>' +
          '<span class="issue-t"><b>' + esc(p.title || '') + '</b><span>' + esc(p.date || '') + ' · ' +
          esc((p.sections || []).length + '개 분야') + '</span></span></button>';
      }).join('') + '</div>',
      foot: '<button class="btn" type="button" data-close>닫기</button>'
    });
    $$('#mBody [data-past]').forEach(function (row) {
      row.addEventListener('click', function () {
        var p = past[Number(row.getAttribute('data-past'))];
        var body = (p.sections || []).map(function (s) {
          return '<div class="brief-sec"><h3><span>' + esc(s.label || '') + '</span>' + esc(s.title || '') + '</h3>' +
            '<p>' + esc(s.body || '') + '</p></div>';
        }).join('');
        openModal({
          eyebrow: 'ARCHIVE · ' + (p.no || ''), title: p.title || '',
          body: '<p class="mb-p">' + esc(p.lead || '') + '</p>' + body,
          foot: '<button class="btn btn-line" type="button" id="backPast">← 목록</button>' +
            '<button class="btn" type="button" data-close>닫기</button>'
        });
        var back = $('#backPast');
        if (back) back.addEventListener('click', pastModal);
      });
    });
  }

  /* --------------------------- TOP 10 --------------------------- */
  function renderTop10() {
    var rows = (DATA.ranks && DATA.ranks.all) || [];
    if (!rows.length) {
      $('#top10List').innerHTML = '<li class="micro-note">수집된 키워드가 없습니다.</li>';
      return;
    }
    var max = rows.reduce(function (a, b) { return Math.max(a, b.r || 0); }, 1);
    $('#top10List').innerHTML = rows.slice(0, 10).map(function (r, i) {
      var w = Math.max(8, Math.round((r.r || 0) / max * 100));
      return '<li><button class="top10-item" type="button" data-kw="' + esc(r.k) + '" data-testid="top10-' + i + '">' +
        '<span class="t10-no">' + String(i + 1).padStart(2, '0') + '</span>' +
        '<span class="t10-body"><span class="t10-k">' + esc(r.k) + '</span>' +
        '<span class="t10-bar"><i style="width:' + w + '%"></i></span></span>' +
        '<span class="t10-r">▲' + (r.r || 0) + '%</span></button></li>';
    }).join('');
    var at = (DATA.ranks.updated_at || '').slice(11, 16);
    var el = $('#top10-time');
    if (el) el.textContent = at ? at + ' 기준' : 'LIVE';
  }

  function applyKeyword(kw) {
    state.kw = kw; state.filter = 'all'; state.q = kw; state.limit = 12;
    var q = $('#q'); if (q) { q.value = kw; $('#qClear').hidden = false; }
    var chip = $('#kwChip');
    if (chip) { chip.hidden = false; $('#kwText').textContent = kw; }
    renderChips(); renderFeed();
    document.getElementById('explore').scrollIntoView({ behavior: 'smooth', block: 'start' });
    toast('‘' + kw + '’ 로 필터했습니다');
  }

  /* --------------------------- 칩 · 피드 --------------------------- */
  function counts() {
    var map = {};
    FEED.forEach(function (f) {
      f.cats.forEach(function (c) { map[c] = (map[c] || 0) + 1; });
    });
    return map;
  }
  function renderChips() {
    var c = counts();
    var chips = [{ key: 'all', label: '전체', n: FEED.length }];
    ['comm', 'news', 'youtube', 'web'].forEach(function (k) {
      if (c[k]) chips.push({ key: k, label: CAT[k].label, n: c[k] });
    });
    TOPIC_ORDER.forEach(function (k) {
      if (c[k]) chips.push({ key: k, label: CAT[k].label, n: c[k] });
    });
    $('#catChips').innerHTML = chips.map(function (x) {
      return '<button class="chip" type="button" role="tab" data-cat="' + x.key + '" data-testid="cat-' + x.key + '" ' +
        'aria-selected="' + (state.filter === x.key) + '">' + esc(x.label) + '<em>' + x.n + '</em></button>';
    }).join('');
  }

  function matchesQuery(f, q) {
    if (!q) return true;
    var hay = [f.title, f.source, (f.section || '')].join(' ').toLowerCase();
    return hay.indexOf(q.toLowerCase()) !== -1;
  }

  function visibleList() {
    var out;
    if (state.savedOnly) {
      out = saved.map(function (s) {
        return itemById(s.id) || {
          id: s.id, cat: s.cat || 'comm', cats: [s.cat || 'comm'], kind: 'post',
          source: s.source, title: s.title, url: s.url, img: s.img, time: '', published: '',
          hot: 0, rise: 0, views: 0, section: '', hue: hashHue(s.title || '')
        };
      });
    } else {
      out = FEED.slice();
    }
    var q = (state.q || '').trim();
    out = out.filter(function (f) {
      if (state.filter !== 'all' && f.cats.indexOf(state.filter) < 0) return false;
      return matchesQuery(f, q);
    });
    out.sort(function (a, b) {
      if (state.sort === 'rise') return (b.rise || 0) - (a.rise || 0);
      if (state.sort === 'new') return String(b.published).localeCompare(String(a.published));
      return (b.hot || 0) - (a.hot || 0);
    });
    // 기본(인기) 화면은 분야를 번갈아 배치해 한 매체가 피드를 독차지하지 않게 합니다.
    if (state.sort === 'hot' && state.filter === 'all' && !state.q && !state.savedOnly) {
      out = interleave(out);
    }
    return out;
  }

  function interleave(list) {
    var buckets = {}, order = [];
    list.forEach(function (f) {
      if (!buckets[f.cat]) { buckets[f.cat] = []; order.push(f.cat); }
      buckets[f.cat].push(f);
    });
    var out = [], i = 0;
    while (out.length < list.length) {
      var added = false;
      for (var k = 0; k < order.length; k++) {
        var b = buckets[order[k]];
        if (b[i]) { out.push(b[i]); added = true; }
      }
      if (!added) break;
      i++;
    }
    return out;
  }

  function feedCard(f) {
    var on = isSaved(f.id);
    var label = CAT[f.cat] ? CAT[f.cat].label : '소식';
    var meta = [];
    if (f.kind === 'shorts') meta.push('SHORTS');
    else if (f.kind === 'video') meta.push('영상');
    if (f.views) meta.push('조회 ' + compact(f.views));
    if (f.time) meta.push(f.time);
    meta.push(f.source);
    return '<article class="pick" data-id="' + esc(f.id) + '">' +
      '<a class="pick-media" href="' + esc(f.url || '#') + '" target="_blank" rel="noopener" aria-label="' + esc(f.title) + ' 원문 열기">' +
        artSvg(f.cat) +
        (f.img ? '<img src="' + esc(f.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async" data-testid="thumb-' + esc(f.id) + '">' : '') +
        '<span class="pick-tag' + (f.kind === 'shorts' || f.kind === 'video' ? ' video' : '') + '">' + esc(label) + '</span>' +
      '</a>' +
      '<button class="pick-save" type="button" data-save="' + esc(f.id) + '" aria-pressed="' + on + '" ' +
        'aria-label="저장" data-testid="save-' + esc(f.id) + '">★</button>' +
      '<div class="pick-body">' +
        '<h3 class="pick-t"><a href="' + esc(f.url || '#') + '" target="_blank" rel="noopener">' + esc(f.title) + '</a></h3>' +
        '<div class="pick-meta">' + meta.filter(Boolean).map(function (m, i) {
          return (i ? '<span class="sep" aria-hidden="true"></span>' : '') + '<span>' + esc(m) + '</span>';
        }).join('') + '</div>' +
      '</div></article>';
  }

  function inFeedAd() {
    if (!(adsenseReady('feed') || adPreview)) return '';
    var inner = adsenseReady('feed')
      ? '<ins class="adsbygoogle" style="display:block" data-ad-client="' + esc(TRENDPICK_ADS.adsense.client) +
        '" data-ad-slot="' + esc(TRENDPICK_ADS.adsense.slots.feed) + '" data-ad-format="fluid" ' +
        'data-ad-layout-key="-fb+5w+4e-db+86"></ins>'
      : '<div class="ad-box"><b>피드 인라인 광고 자리</b><span>반응형 · 카드 사이에 자연스럽게 들어갑니다</span>' +
        '<span>TRENDPICK_ADS.adsense.slots.feed</span></div>';
    return '<div class="pick-ad" data-ad-inline="1"><div class="ad-label">AD · 피드 인라인</div>' + inner + '</div>';
  }

  function renderFeed() {
    var list = visibleList();
    var shown = list.slice(0, state.limit);
    var html = shown.map(feedCard).join('');
    if (list.length > 6) html = shown.slice(0, 6).map(feedCard).join('') + inFeedAd() +
      shown.slice(6).map(feedCard).join('');
    $('#feedGrid').innerHTML = html || ('<div class="empty"><b>조건에 맞는 픽이 없습니다</b>' +
      (state.savedOnly ? '카드의 ★ 를 눌러 소재를 저장해 보세요.' : '검색어나 분야를 바꿔 보세요.') + '</div>');

    var note = $('#resultNote');
    if (state.savedOnly) note.innerHTML = '저장한 픽 <b>' + list.length + '</b>건';
    else if (state.q) note.innerHTML = '‘' + esc(state.q) + '’ 검색 결과 <b>' + list.length + '</b>건';
    else if (state.filter !== 'all') note.innerHTML = esc(CAT[state.filter].label) + ' <b>' + list.length + '</b>건';
    else note.innerHTML = '전체 <b>' + list.length + '</b>건 · ' +
      (state.sort === 'rise' ? '급상승 순' : state.sort === 'new' ? '최신 순' : '인기 순');

    var more = $('#moreBtn');
    if (list.length > state.limit) {
      more.hidden = false;
      more.textContent = '더 보기 (' + (list.length - state.limit) + '건)';
    } else if (state.limit > 12 && list.length > 12) {
      more.hidden = false;
      more.textContent = '접기';
    } else {
      more.hidden = true;
    }
  }

  /* --------------------------- 뉴스 --------------------------- */
  function renderNews() {
    var news = (DATA.news || []).filter(function (n) { return !n.noise; });
    var secs = ['전체'].concat(Object.keys(news.reduce(function (m, n) {
      if (n.section) m[n.section] = 1; return m;
    }, {})));
    $('#newsTabs').innerHTML = secs.map(function (s) {
      return '<button class="chip" type="button" role="tab" data-news="' + esc(s) + '" ' +
        'aria-selected="' + (state.newsSec === s) + '">' + esc(s) + '</button>';
    }).join('');
    var list = news.filter(function (n) {
      return state.newsSec === '전체' || n.section === state.newsSec;
    }).slice(0, state.newsSec === '전체' ? 8 : 10);
    $('#newsList').innerHTML = list.length ? list.map(function (n) {
      return '<a class="news-item" href="' + esc(n.url || '#') + '" target="_blank" rel="noopener" data-testid="news-' + esc(n.id) + '">' +
        '<span class="n-thumb">' + artSvg('news') +
          (n.img ? '<img src="' + esc(n.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
        '</span>' +
        '<span class="n-body"><span class="n-sec">' + esc(n.section || '뉴스') + '</span>' +
        '<span class="n-t">' + esc(n.title) + '</span>' +
        '<span class="n-meta">' + esc(n.source || '') + ' · ' + esc(n.time || '') + '</span></span></a>';
    }).join('') : '<div class="empty"><b>수집된 뉴스가 없습니다</b>잠시 후 자동 수집에서 다시 채워집니다.</div>';
  }

  /* --------------------------- 유튜브 --------------------------- */
  function renderYoutube() {
    var vids = DATA.videos || [];
    $('#ytNote').textContent = (DATA.youtube_mode === 'api' ? '실시간 인기 급상승' : '유튜브 · 최신 업로드') +
      (vids.length ? ' · ' + vids.length + '편' : '');
    $('#ytRail').innerHTML = vids.length ? vids.map(function (v, i) {
      return '<a class="yt-card" href="' + esc(v.url || '#') + '" target="_blank" rel="noopener" data-testid="yt-' + i + '">' +
        '<span class="yt-thumb">' + artSvg('youtube') +
          (v.img ? '<img src="' + esc(v.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
          (v.kind === 'shorts' ? '<span class="yt-badge">SHORTS</span>' : '') +
          '<span class="yt-play" aria-hidden="true">▶</span></span>' +
        '<span class="yt-t">' + esc(v.title) + '</span>' +
        '<span class="yt-m">' + esc(v.channel || '') + ' · ' + esc(v.time || '') + '</span></a>';
    }).join('') : '<div class="empty"><b>영상이 없습니다</b>채널 RSS 수집을 확인하세요.</div>';
  }

  /* --------------------------- 특가 · 핫딜 --------------------------- */
  function renderDeals() {
    var deals = DATA.deals || [];
    var grid = $('#dealGrid');
    if (deals.length) {
      $('#dealNote').textContent = '네이버 쇼핑 최저가 · ' + deals.length + '건';
      grid.innerHTML = deals.slice(0, 6).map(function (d) {
        return '<a class="deal" href="' + esc(d.url || '#') + '" target="_blank" rel="noopener">' +
          '<span class="deal-thumb">' + artSvg('deal') +
            (d.img ? '<img src="' + esc(d.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
          '</span><span class="deal-body"><span class="deal-name">' + esc(d.name) + '</span>' +
          '<span class="deal-price">' + won(d.price) + '</span>' +
          '<span class="deal-store">' + esc(d.store || '') + '</span></span></a>';
      }).join('');
      return;
    }
    // 네이버 쇼핑 API 키가 없을 때: 가짜 가격 대신 실제 수집된 할인·특가 소식을 보여 줍니다.
    var rows = FEED.filter(function (f) { return f.cats.indexOf('apptech') >= 0; }).slice(0, 6);
    var section = document.getElementById('deal');
    if (!rows.length) {
      // 키도 없고 오늘 수집된 할인 소식도 없으면 빈 상자를 남기지 않고 섹션을 접습니다.
      if (section) section.hidden = true;
      return;
    }
    if (section) section.hidden = false;
    $('#dealNote').textContent = '오늘 수집된 할인·특가 소식';
    grid.innerHTML = rows.length ? rows.map(function (f) {
      return '<a class="deal" href="' + esc(f.url || '#') + '" target="_blank" rel="noopener">' +
        '<span class="deal-thumb">' + artSvg('apptech') +
          (f.img ? '<img src="' + esc(f.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
        '</span><span class="deal-body"><span class="deal-name">' + esc(f.title) + '</span>' +
        '<span class="deal-store">' + esc(f.source) + ' · ' + esc(f.time || '') + '</span></span></a>';
    }).join('') : '<div class="empty" style="grid-column:1/-1"><b>오늘은 할인 소식이 적습니다</b>' +
      '네이버 쇼핑 API 키를 연결하면 실제 최저가 목록이 이 자리에 채워집니다.</div>';
  }

  /* --------------------------- 오픈소스 · 앱 · 해커톤 --------------------------- */
  function renderOpensource() {
    var list = DATA.opensource || [];
    $('#osList').innerHTML = list.length ? list.slice(0, 6).map(function (o, i) {
      return '<a class="os-item" href="' + esc(o.url || '#') + '" target="_blank" rel="noopener" data-testid="os-' + i + '">' +
        '<span class="os-ico">' + artSvg('os') +
          (o.img ? '<img src="' + esc(o.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
        '</span><span class="os-body"><span class="os-repo">' + esc(o.repo) + '</span>' +
        '<span class="os-desc">' + esc(o.desc || o.lang || '') + '</span></span>' +
        '<span class="os-star">★ ' + compact(o.stars || 0) + '</span></a>';
    }).join('') : '<div class="empty"><b>트렌딩을 가져오지 못했습니다</b>잠시 후 다시 확인합니다.</div>';
  }

  function renderApps() {
    var apps = DATA.apps || [];
    var platforms = [];
    apps.forEach(function (a) { if (a.platform && platforms.indexOf(a.platform) < 0) platforms.push(a.platform); });
    if (!state.appTab || platforms.indexOf(state.appTab) < 0) state.appTab = platforms[0] || '';
    $('#appTabs').innerHTML = platforms.map(function (p) {
      return '<button class="chip" type="button" role="tab" data-app="' + esc(p) + '" ' +
        'aria-selected="' + (state.appTab === p) + '">' + esc(p) + '</button>';
    }).join('');
    var list = apps.filter(function (a) { return a.platform === state.appTab; });
    $('#appList').innerHTML = list.length ? list.slice(0, 10).map(function (a, i) {
      return '<a class="app-item" href="' + esc(a.url || '#') + '" target="_blank" rel="noopener">' +
        '<span class="ap-rank">' + (a.rank || i + 1) + '</span>' +
        '<span class="ap-ico">' + artSvg('apps') +
          (a.img ? '<img src="' + esc(a.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
        '</span><span class="ap-body"><span class="ap-n">' + esc(a.name) + '</span>' +
        '<span class="ap-c">' + esc(a.category || '') + '</span></span></a>';
    }).join('') : '<div class="empty"><b>순위를 가져오지 못했습니다</b>앱스토어·스팀 응답을 확인하세요.</div>';
  }

  function renderHackathons() {
    var list = DATA.hackathons || [];
    $('#hackList').innerHTML = list.length ? list.slice(0, 6).map(function (h, i) {
      return '<a class="hack" href="' + esc(h.url || '#') + '" target="_blank" rel="noopener" data-testid="hack-' + i + '">' +
        '<span class="hack-thumb">' + artSvg('hack') +
          (h.img ? '<img src="' + esc(h.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
          '<span class="hack-dday">' + esc(h.dday || '모집중') + '</span></span>' +
        '<span class="hack-body"><span class="hack-n">' + esc(h.name) + '</span>' +
        '<span class="hack-m">' + esc(h.host || '') + (h.prize ? ' · ' + esc(h.prize) : '') + '</span></span></a>';
    }).join('') : '<div class="empty" style="grid-column:1/-1"><b>모집 중인 공모전이 없습니다</b>다음 수집에서 다시 확인합니다.</div>';
  }

  /* --------------------------- 수집 현황 · 모드 --------------------------- */
  function renderStats() {
    var st = DATA.stats || {};
    var th = (DATA.thumbs && DATA.thumbs.all) || {};
    var gen = (DATA.generated_at || '').replace('T', ' ').slice(5, 16);
    var rows = [
      ['수집 출처', (st.live_sources || st.sources || 0) + '곳'],
      ['수집 항목', (st.collected || FEED.length) + '건'],
      ['썸네일', th.rate ? Math.round(th.rate * 100) + '%' : '-'],
      ['마지막 갱신', gen || '-']
    ];
    $('#statList').innerHTML = rows.map(function (r) {
      return '<dt>' + esc(r[0]) + '</dt><dd>' + esc(r[1]) + '</dd>';
    }).join('');
    $('#statLive').textContent = MODE === 'live' ? 'LIVE' : 'SNAPSHOT';
    var skipped = (DATA.collect_log || []).filter(function (r) {
      return r.status === 'skip' || r.status === 'error';
    });
    $('#statNote').textContent = skipped.length
      ? '이번 수집에서 ' + skipped.length + '개 소스가 응답하지 않아 건너뛰었습니다(나머지는 정상).'
      : '모든 수집 소스가 정상 응답했습니다. 하루 두 번 자동으로 갱신됩니다.';
    var stamp = $('#footStamp');
    if (stamp) stamp.textContent = '© ' + (DATA.issue && DATA.issue.date ? DATA.issue.date.slice(0, 4) : '2026') + ' TrendPick';
    var repo = (DATA.site && DATA.site.repo) || 'econature7-lab/nori-traffic-scent';
    var link = $('#repoLink');
    if (link) link.href = 'https://github.com/' + repo;
  }

  /* --------------------------- 모달 --------------------------- */
  var lastFocus = null;
  function openModal(o) {
    lastFocus = document.activeElement;
    $('#mEyebrow').textContent = o.eyebrow || '';
    $('#mTitle').textContent = o.title || '';
    $('#mBody').innerHTML = o.body || '';
    $('#mFoot').innerHTML = o.foot || '';
    $('#modal').hidden = false;
    document.body.style.overflow = 'hidden';
    var x = $('.modal-x'); if (x) x.focus({ preventScroll: true });
    $('#mBody').scrollTop = 0;
  }
  function closeModal() {
    $('#modal').hidden = true;
    document.body.style.overflow = '';
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus({ preventScroll: true }); } catch (e) {} }
  }

  /* --------------------------- 이벤트 --------------------------- */
  function bind() {
    // 검색
    var q = $('#q');
    q.addEventListener('input', function () {
      state.q = q.value; state.kw = ''; state.limit = 12;
      $('#qClear').hidden = !q.value;
      var chip = $('#kwChip'); if (chip) chip.hidden = !state.kw;
      renderFeed();
    });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); document.getElementById('explore').scrollIntoView({ behavior: 'smooth' }); }
      if (e.key === 'Escape') { q.value = ''; state.q = ''; $('#qClear').hidden = true; renderFeed(); }
    });
    $('#qClear').addEventListener('click', function () {
      q.value = ''; state.q = ''; state.kw = ''; $('#qClear').hidden = true;
      $('#kwChip').hidden = true; renderFeed(); q.focus();
    });
    $('#kwChip').addEventListener('click', function () {
      state.kw = ''; state.q = ''; q.value = ''; $('#qClear').hidden = true;
      this.hidden = true; renderFeed();
    });

    // 분야 칩
    $('#catChips').addEventListener('click', function (e) {
      var b = e.target.closest('[data-cat]');
      if (!b) return;
      state.filter = b.getAttribute('data-cat');
      state.limit = 12;
      renderChips(); renderFeed();
    });

    // 정렬
    [['#sortHot', 'hot'], ['#sortRise', 'rise'], ['#sortNew', 'new']].forEach(function (pair) {
      $(pair[0]).addEventListener('click', function () {
        state.sort = pair[1];
        [['#sortHot', 'hot'], ['#sortRise', 'rise'], ['#sortNew', 'new']].forEach(function (p) {
          $(p[0]).setAttribute('aria-pressed', String(p[1] === state.sort));
        });
        renderFeed();
      });
    });

    // 더 보기
    $('#moreBtn').addEventListener('click', function () {
      var total = visibleList().length;
      if (state.limit >= total) state.limit = 12;
      else state.limit = Math.min(total, state.limit + 12);
      renderFeed();
    });

    // 저장
    $('#feedGrid').addEventListener('click', function (e) {
      var b = e.target.closest('[data-save]');
      if (!b) return;
      e.preventDefault(); e.stopPropagation();
      toggleSaved(b.getAttribute('data-save'));
    });
    $('#savedBtn').addEventListener('click', function () {
      state.savedOnly = !state.savedOnly;
      state.filter = 'all'; state.limit = 12;
      renderChips(); refreshSaved(); renderFeed();
      if (state.savedOnly) {
        document.getElementById('explore').scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (!saved.length) toast('아직 저장한 픽이 없습니다 · 카드의 ★ 를 눌러 보세요');
      }
    });
    $('#savedChip').addEventListener('click', function () {
      state.savedOnly = false;
      refreshSaved(); renderFeed();
    });

    // TOP 10 키워드
    $('#top10List').addEventListener('click', function (e) {
      var b = e.target.closest('[data-kw]');
      if (b) applyKeyword(b.getAttribute('data-kw'));
    });

    // 브리프
    $('#bOpen').addEventListener('click', briefModal);
    $('#bPast').addEventListener('click', pastModal);
    $('#brief').addEventListener('click', function (e) {
      if (e.target.closest('#bOpen') || e.target.closest('#bPast') || e.target.closest('a')) return;
      var spine = e.target.closest('.spine');
      if (spine) briefModal();
    });

    // 뉴스 탭
    $('#newsTabs').addEventListener('click', function (e) {
      var b = e.target.closest('[data-news]');
      if (!b) return;
      state.newsSec = b.getAttribute('data-news');
      renderNews();
    });

    // 앱 탭
    $('#appTabs').addEventListener('click', function (e) {
      var b = e.target.closest('[data-app]');
      if (!b) return;
      state.appTab = b.getAttribute('data-app');
      renderApps();
    });

    // 광고 미리보기
    $('#adPreviewBtn').addEventListener('click', function () {
      adPreview = !adPreview;
      renderAds(); renderFeed();
      toast(adPreview ? '광고 자리 미리보기를 켰습니다 · 실제 광고는 ID를 넣으면 나옵니다' : '광고 자리 미리보기를 껐습니다');
    });

    // 모달
    $('#modal').addEventListener('click', function (e) {
      if (e.target.closest('[data-close]')) closeModal();
    });

    // 키보드
    document.addEventListener('keydown', function (e) {
      var k = (e.key || '').toLowerCase();
      if ((e.metaKey || e.ctrlKey) && k === 'k') {
        e.preventDefault();
        q.focus(); q.select();
        return;
      }
      if (e.key === 'Escape' && !$('#modal').hidden) closeModal();
    });

    // 이미지 로드 실패 → 일러스트 카드로 대체 (깨진 이미지 없음)
    document.addEventListener('error', function (e) {
      var el = e.target;
      if (el && el.tagName === 'IMG') {
        el.classList.add('is-broken');
        el.setAttribute('data-broken', '1');
      }
    }, true);
  }

  /* --------------------------- 부팅 --------------------------- */
  function renderAll() {
    renderBrief();
    renderTop10();
    renderChips();
    renderFeed();
    renderNews();
    renderYoutube();
    renderDeals();
    renderOpensource();
    renderApps();
    renderHackathons();
    renderStats();
    refreshSaved();
    renderAds();
  }

  function boot() {
    // 화면을 먼저 그린 뒤(내장 스냅샷) data.json 이 있으면 최신 값으로 교체
    renderAll();
    bind();

    if (/^https?:/.test(location.protocol)) {
      fetch('./data.json', { cache: 'no-store' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (json) {
          if (!json || !Array.isArray(json.posts) || !json.posts.length) return;
          DATA = Object.assign({}, EMBEDDED, json);
          FEED = normalize();
          MODE = 'live';
          state.limit = 12;
          renderAll();
        })
        .catch(function () { /* data.json 없음 → 내장 스냅샷 유지 */ });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
