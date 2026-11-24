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

  /* ------------------------------------------------------------------
     제휴(affiliate) 설정 — 쿠팡 파트너스
     · #deal(특가·핫딜) 섹션 안에서만 노출됩니다. (뉴스·커뮤니티·광고 영역 미오염)
     · coupangId 는 파트너스 추적 ID, 실제 수익 링크는 아래 TRENDPICK_DEAL_LINKS 에
       단축링크(https://link.coupang.com/a/...)를 상품명/키워드와 함께 넣으면 그 링크가 우선 쓰입니다.
       매핑이 없으면 쿠팡 최저가 비교 검색(/np/search?q=상품명)으로 연결됩니다.
     · enabled:false 로 두면 고지·링크·검색창이 모두 사라집니다.
  ------------------------------------------------------------------ */
  var TRENDPICK_AFFILIATE = {
    enabled: true,
    coupangId: 'AF2392399',
    notice: '이 영역에는 쿠팡 파트너스 활동의 일환으로 일정액의 수수료를 제공받는 제휴 링크가 포함될 수 있습니다.'
  };

  // 파트너스 단축링크 수동 매핑 슬롯 — 예: '무선 청소기': 'https://link.coupang.com/a/abcd1234'
  var TRENDPICK_DEAL_LINKS = {
    // '상품명 또는 키워드': 'https://link.coupang.com/a/단축코드',
  };

  var SITE_URL = 'https://econature7-lab.github.io/nori-traffic-scent/';

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

  /* 클립보드 — navigator.clipboard 실패 시 textarea 폴백 */
  function fallbackCopy(text) {
    try {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, text.length);
      var ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return !!ok;
    } catch (e) { return false; }
  }
  function copyText(text, okMsg) {
    function done(ok) {
      if (ok) toast(okMsg || '복사했습니다 · 붙여넣기만 하면 돼요');
      else toast('복사가 막혔습니다 · 본문을 길게 눌러 직접 복사해 주세요');
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(fallbackCopy(text)); });
    } else {
      done(fallbackCopy(text));
    }
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
    deal:     { label: '핫딜' },
    econ:     { label: '경제·증시' },
    social:   { label: '사회·생활' }
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

  /* ------------------ 카테고리별 에디토리얼 커버 ------------------
     이미지가 없는 카드는 분야별 딥톤 그라데이션 + 잡지 표지형 타이포그래피로 그립니다.
     색은 채도를 낮춘 딥톤만 사용하고, 글자는 흰색 → 대비 7:1 이상 확보.  */
  var ART = {
    comm:    { a: '#1B2430', b: '#3A4C61', en: 'COMMUNITY' },
    news:    { a: '#14243A', b: '#2E4E6E', en: 'NEWSROOM' },
    econ:    { a: '#14342C', b: '#2A6553', en: 'MARKET' },
    social:  { a: '#1E2B2E', b: '#3E5257', en: 'LIFE' },
    youtube: { a: '#3E1220', b: '#7C2442', en: 'VIDEO' },
    web:     { a: '#1A2350', b: '#38477F', en: 'BLOG' },
    mom:     { a: '#22331F', b: '#46603B', en: 'FAMILY' },
    estate:  { a: '#2B2140', b: '#503B75', en: 'PROPERTY' },
    ai:      { a: '#0D3335', b: '#166068', en: 'AI' },
    apptech: { a: '#3B2A10', b: '#6F4E1C', en: 'APPTECH' },
    build:   { a: '#33301C', b: '#615C35', en: 'BUILD' },
    apps:    { a: '#1E2350', b: '#3C428C', en: 'APPS' },
    os:      { a: '#1F2124', b: '#3C4046', en: 'OPEN SOURCE' },
    hack:    { a: '#3C1B18', b: '#703229', en: 'CHALLENGE' },
    deal:    { a: '#3A0E26', b: '#701D46', en: 'DEALS' }
  };

  // 뉴스 섹션 → 커버 카테고리
  function sectionCat(section) {
    var s = String(section || '');
    if (s.indexOf('경제') >= 0) return 'econ';
    if (s.indexOf('IT') >= 0 || s.indexOf('AI') >= 0) return 'ai';
    if (s.indexOf('부동산') >= 0) return 'estate';
    if (s.indexOf('사회') >= 0) return 'social';
    return 'news';
  }

  function artSvg(cat, seed) {
    var a = ART[cat] || ART.news;
    var v = Math.abs(hashHue(String(seed || cat))) % 3;
    var label = (CAT[cat] && CAT[cat].label) || (ART[cat] ? ART[cat].en : '트렌드');
    return '<span class="art art--' + esc(cat) + ' v' + v + '" aria-hidden="true">' +
      '<svg viewBox="0 0 320 180" preserveAspectRatio="xMinYMax slice" focusable="false">' +
        '<g fill="none" stroke="#fff" stroke-opacity=".16">' +
          '<circle cx="272" cy="22" r="74"/><circle cx="272" cy="22" r="45"/>' +
          '<circle cx="272" cy="22" r="17"/>' +
        '</g>' +
        '<g stroke="#fff" stroke-opacity=".09"><path d="M206 180 320 58"/><path d="M240 180 320 92"/></g>' +
        '<circle cx="272" cy="22" r="3.6" fill="#fff" fill-opacity=".55"/>' +
      '</svg>' +
      '<span class="art-lbl"><i>' + esc(a.en) + '</i><b>' + esc(label) + '</b></span>' +
      '<span class="art-mono">' + esc((a.en || 'T').slice(0, 1)) + '</span>' +
      '<span class="art-mark">TRENDPICK</span></span>';
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
  function briefParagraphs(b) {
    var paras = (b.paragraphs || []).filter(function (p) { return p && String(p).trim(); });
    if (!paras.length && b.lead) paras = [b.lead];
    return paras;
  }

  function briefHighlights(b) {
    if (b.highlights && b.highlights.length) return b.highlights.slice(0, 3);
    // 하이라이트가 없는 예전 데이터: 분야별 첫 포인트를 그대로 씁니다.
    return (b.sections || []).slice(0, 3).map(function (s) {
      var p = (s.points || [])[0];
      return {
        label: s.label || '',
        text: (typeof p === 'string' ? p : (p && p.text)) || s.title || '',
        url: (typeof p === 'string' ? '' : (p && p.url)) || ''
      };
    });
  }

  function renderBrief() {
    var b = DATA.brief || {};
    var issue = DATA.issue || {};
    var st = DATA.stats || {};
    var gen = (DATA.generated_at || '').replace('T', ' ').slice(0, 16);
    $('#bNo').textContent = b.no || ('No.' + String(issue.no || 1).padStart(2, '0'));
    $('#bDate').textContent = (b.label || '') + (b.weekday ? ' ' + b.weekday : '');
    $('#bEyebrow').textContent = '오늘의 트렌드픽 브리프 · ' + (b.date || issue.date || '');

    // 제호는 편집 헤드라인(b.title) 우선, 없으면 대표 기사 제목
    var picks = b.picks || [];
    var lead = picks[0] || { title: b.title || '', url: '', img: '', label: '', source: '' };
    $('#bTitle').textContent = b.title || lead.title || '오늘의 트렌드픽 브리프';
    $('#bLead').textContent = b.lead || '';

    // 핵심 포인트 3줄 — 오늘의 이슈를 한 문장씩
    var hl = briefHighlights(b);
    $('#bPoints').innerHTML = hl.length ? hl.map(function (h, i) {
      var tag = h.url ? 'a' : 'div';
      return '<' + tag + ' class="bp-item"' + (h.url ? ' href="' + esc(h.url) + '" target="_blank" rel="noopener"' : '') +
        ' data-testid="brief-point-' + i + '"><span class="bp-k">' +
        '<em>' + String(i + 1).padStart(2, '0') + '</em>' + esc(h.label || '') + '</span>' +
        '<span class="bp-t">' + esc(h.text || '') + '</span></' + tag + '>';
    }).join('') : '';

    // 헤드라인은 대표 기사, 그 아래 핵픽 3선(서로 다른 분야 우선)
    var hotPicks = picks.slice(1, 4);
    $('#bPicks').innerHTML = hotPicks.map(function (p, i) {
      var cat = p.label === '커뮤니티' ? 'comm' : sectionCat(p.label);
      return '<li><a class="pick-row" href="' + esc(p.url || '#') + '" target="_blank" rel="noopener" data-testid="brief-pick-' + i + '">' +
        '<span class="pick-no">' + String(i + 1).padStart(2, '0') + '</span>' +
        '<span class="pick-thumb">' + artSvg(cat, p.title) +
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

    renderBriefDeep(b, bits, items);
  }

  /* 브리프 전문 — 페이지 본문에 그대로 실어 읽을거리를 확보합니다. */
  function renderBriefDeep(b, bits, items) {
    var host = $('#bdMain');
    if (!host) return;
    var paras = briefParagraphs(b);
    var meta = $('#bdMeta');
    if (meta) {
      meta.textContent = [(b.no || ''), (b.date || ''), items ? '수집 ' + items + '건' : ''].filter(Boolean).join(' · ');
    }
    host.innerHTML = paras.map(function (p, i) {
      return '<p class="bd-p' + (i === 0 ? ' bd-p-lead' : '') + '">' + esc(p) + '</p>';
    }).join('') || '<p class="bd-p">오늘 수집된 이슈로 브리프를 준비하고 있습니다.</p>';

    var secs = (b.sections || []).slice(0, 6);
    $('#bdSecs').innerHTML = secs.map(function (s, i) {
      var points = (s.points || []).slice(0, 3).map(function (p) {
        var text = typeof p === 'string' ? p : p.text;
        var url = typeof p === 'string' ? '' : p.url;
        return '<li>' + (url
          ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(text) + '</a>'
          : esc(text)) + '</li>';
      }).join('');
      return '<article class="bd-sec" data-testid="bd-sec-' + i + '">' +
        '<h3><span>' + esc(s.label || '') + '</span>' + esc(s.title || '') + '</h3>' +
        '<p>' + esc(s.body || '') + '</p>' +
        (points ? '<ul>' + points + '</ul>' : '') + '</article>';
    }).join('');

    var note = $('#bdNote');
    if (note) {
      note.textContent = '공개 RSS·API 로 수집한 제목과 수치만 근거로 쓴 오늘의 편집 브리프입니다. 원문과 전체 맥락은 각 항목의 링크에서 확인하세요.' +
        (b.engine && String(b.engine).indexOf('gemini') === 0 ? ' 문장 다듬기: Gemini Flash.' : '') +
        (bits && bits.length ? ' · ' + bits.join(' · ') : '');
    }
  }

  function briefModal() {
    var b = DATA.brief || {};
    var paras = briefParagraphs(b);
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
      title: b.title || '오늘의 트렌드픽 브리프',
      body: paras.map(function (p) { return '<p class="mb-p">' + esc(p) + '</p>'; }).join('') +
        (secs || '<p class="mb-p">수집된 이슈가 없습니다.</p>') +
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
      syncSearchChip();
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
    var q = $('#q'); if (q) q.value = kw;
    renderChips(); syncSearchChip(); renderFeed();
    scrollToResults();
    toast('‘' + kw + '’ 로 필터했습니다');
  }

  /* 검색 상태(입력값 · 지우기 버튼 · 결과 칩)를 한 곳에서 맞춥니다. */
  function syncSearchChip() {
    var q = $('#q'), term = (state.q || '').trim();
    var x = $('#qClear'); if (x) x.hidden = !(q && q.value);
    var chip = $('#qChip');
    if (chip) {
      chip.hidden = !term;
      if (term) { var t = $('#qChipText'); if (t) t.textContent = term; }
    }
  }

  function scrollToResults() {
    var target = document.getElementById('explore');
    if (!target) return;
    try { target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    catch (e) { target.scrollIntoView(); }
  }

  function clearSearch(keepFocus) {
    state.q = ''; state.kw = '';
    var q = $('#q'); if (q) q.value = '';
    syncSearchChip(); renderFeed();
    if (keepFocus && q) q.focus();
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
    // 뉴스 카드는 분야별 커버(경제·증시/IT·AI/부동산·정책/사회·생활)로 색을 나눕니다
    var artCat = f.cat === 'news' ? sectionCat(f.section) : f.cat;
    var meta = [];
    if (f.kind === 'shorts') meta.push('SHORTS');
    else if (f.kind === 'video') meta.push('영상');
    if (f.views) meta.push('조회 ' + compact(f.views));
    if (f.time) meta.push(f.time);
    meta.push(f.source);
    return '<article class="pick" data-id="' + esc(f.id) + '">' +
      '<a class="pick-media" href="' + esc(f.url || '#') + '" target="_blank" rel="noopener" aria-label="' + esc(f.title) + ' 원문 열기">' +
        artSvg(artCat, f.title) +
        (f.img ? '<img src="' + esc(f.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async" data-testid="thumb-' + esc(f.id) + '">' : '') +
        (f.img || f.kind === 'video' || f.kind === 'shorts'
          ? '<span class="pick-tag' + (f.kind === 'shorts' || f.kind === 'video' ? ' video' : '') + '">' + esc(label) + '</span>'
          : '') +
      '</a>' +
      '<button class="pick-save" type="button" data-save="' + esc(f.id) + '" aria-pressed="' + on + '" ' +
        'aria-label="저장" data-testid="save-' + esc(f.id) + '">★</button>' +
      '<button class="pick-copy" type="button" data-copy="' + esc(f.id) + '" ' +
        'aria-label="글감 복사" title="X·블로그 글감으로 복사" data-testid="copy-' + esc(f.id) + '">📋</button>' +
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
    var qText = (state.q || '').trim();
    if (note) note.classList.toggle('is-search', !!qText);
    if (state.savedOnly) note.innerHTML = '저장한 픽 <b>' + list.length + '</b>건';
    else if (qText) note.innerHTML = '‘' + esc(qText) + '’ 검색 결과 <b>' + list.length + '</b>건';
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
        '<span class="n-thumb">' + artSvg(sectionCat(n.section), n.title) +
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
        '<span class="yt-thumb">' + artSvg('youtube', v.title) +
          (v.img ? '<img src="' + esc(v.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
          (v.kind === 'shorts' ? '<span class="yt-badge">SHORTS</span>' : '') +
          '<span class="yt-play" aria-hidden="true">▶</span></span>' +
        '<span class="yt-t">' + esc(v.title) + '</span>' +
        '<span class="yt-m">' + esc(v.channel || '') + ' · ' + esc(v.time || '') + '</span></a>';
    }).join('') : '<div class="empty"><b>영상이 없습니다</b>채널 RSS 수집을 확인하세요.</div>';
  }

  /* --------------------------- 특가 · 핫딜 (쿠팡 제휴) --------------------------- */
  var DEAL_ROWS = [];

  function coupangSearch(q) {
    return 'https://www.coupang.com/np/search?q=' + encodeURIComponent(q || '');
  }
  function affiliateUrl(name) {
    if (!TRENDPICK_AFFILIATE.enabled) return '';
    var key = String(name || '').trim();
    if (!key) return '';
    var map = TRENDPICK_DEAL_LINKS || {};
    for (var k in map) {
      if (!Object.prototype.hasOwnProperty.call(map, k)) continue;
      if (map[k] && key.indexOf(k) >= 0) return map[k];
    }
    return coupangSearch(key);
  }
  function dealCopyText(d) {
    var name = d.name || d.title || '';
    var lines = ['[핫딜] ' + name];
    if (d.price) lines.push('가격: ' + won(d.price));
    if (d.store) lines.push('판매처: ' + d.store);
    if (d.url) lines.push('원문: ' + d.url);
    var cp = affiliateUrl(name);
    if (cp) lines.push('쿠팡 최저가 비교: ' + cp);
    lines.push('');
    lines.push('※ 쿠팡 파트너스 활동의 일환으로 일정액의 수수료를 받을 수 있습니다.');
    lines.push('오늘 브리프 더 보기 → ' + SITE_URL);
    return lines.join('\n');
  }
  function dealCard(d, i, kind) {
    var name = d.name || d.title || '';
    var aff = affiliateUrl(name);
    var body = kind === 'deal'
      ? '<span class="deal-body"><span class="deal-name">' + esc(name) + '</span>' +
        (d.price ? '<span class="deal-price">' + won(d.price) + '</span>' : '') +
        '<span class="deal-store">' + esc(d.store || '') + '</span></span>'
      : '<span class="deal-body"><span class="deal-name">' + esc(name) + '</span>' +
        '<span class="deal-store">' + esc(d.source || '') + (d.time ? ' · ' + esc(d.time) : '') + '</span></span>';
    return '<article class="deal-cell">' +
      '<a class="deal" href="' + esc(d.url || aff || '#') + '" target="_blank" rel="noopener">' +
        '<span class="deal-thumb">' + artSvg(kind === 'deal' ? 'deal' : 'apptech', name) +
          (d.img ? '<img src="' + esc(d.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
        '</span>' + body + '</a>' +
      '<div class="deal-acts">' +
        (aff ? '<a class="deal-coupang" href="' + esc(aff) + '" target="_blank" rel="noopener sponsored" data-testid="coupang-' + i + '">쿠팡 최저가 <span aria-hidden="true">↗</span></a>' : '') +
        '<button class="deal-copy" type="button" data-deal-copy="' + i + '" data-testid="deal-copy-' + i + '">📋 글감</button>' +
      '</div></article>';
  }

  function renderCoupangSearch() {
    var box = $('#coupangSearch');
    if (!box) return;
    if (!TRENDPICK_AFFILIATE.enabled) { box.hidden = true; return; }
    box.hidden = false;
    if (box.getAttribute('data-ready') === '1') return;
    box.innerHTML =
      '<label class="cp-label" for="cpQ">쿠팡 최저가 비교 검색 <em>제휴</em></label>' +
      '<form class="cp-row" id="cpForm" role="search">' +
        '<input id="cpQ" type="search" autocomplete="off" placeholder="상품명을 넣으면 쿠팡 최저가로 바로 갑니다" data-testid="coupang-q">' +
        '<button class="btn btn-ink" type="submit" data-testid="coupang-go">검색</button>' +
      '</form>' +
      '<p class="micro-note">쿠팡 파트너스 제휴 링크입니다. 구매가 이뤄지면 일정액의 수수료를 받을 수 있고, 가격은 쿠팡에서 그대로 확인됩니다.</p>';
    box.setAttribute('data-ready', '1');
    $('#cpForm').addEventListener('submit', function (e) {
      e.preventDefault();
      var q = ($('#cpQ').value || '').trim();
      if (!q) { toast('찾을 상품명을 적어 주세요'); $('#cpQ').focus(); return; }
      window.open(coupangSearch(q), '_blank', 'noopener');
    });
  }

  function renderDeals() {
    var note = $('#affNote');
    if (note) {
      note.textContent = TRENDPICK_AFFILIATE.enabled ? TRENDPICK_AFFILIATE.notice : '';
      note.hidden = !TRENDPICK_AFFILIATE.enabled;
    }
    var section = document.getElementById('deal');
    var grid = $('#dealGrid');
    var deals = DATA.deals || [];

    if (deals.length) {
      DEAL_ROWS = deals.slice(0, 6).map(function (d) {
        return { name: d.name, price: d.price, store: d.store, url: d.url, img: d.img };
      });
      $('#dealNote').textContent = '네이버 쇼핑 최저가 · ' + deals.length + '건';
      grid.innerHTML = DEAL_ROWS.map(function (d, i) { return dealCard(d, i, 'deal'); }).join('');
    } else {
      // 네이버 쇼핑 API 키가 없을 때: 가짜 가격 대신 실제 수집된 할인·특가 소식을 그대로 씁니다.
      var rows = FEED.filter(function (f) { return f.cats.indexOf('apptech') >= 0; }).slice(0, 6);
      DEAL_ROWS = rows.map(function (f) {
        return { name: f.title, store: f.source, time: f.time, url: f.url, img: f.img, source: f.source };
      });
      if (DEAL_ROWS.length) {
        $('#dealNote').textContent = '오늘 수집된 할인·특가 소식';
        grid.innerHTML = DEAL_ROWS.map(function (d, i) { return dealCard(d, i, 'news'); }).join('');
      } else {
        DEAL_ROWS = [];
        $('#dealNote').textContent = '오늘은 할인 소식이 적은 날';
        grid.innerHTML = '<div class="empty empty-slim" style="grid-column:1/-1"><b>오늘 수집된 할인·특가 소식이 없습니다</b>' +
          '아래 쿠팡 최저가 검색에서 원하는 상품을 바로 비교해 볼 수 있습니다.</div>';
      }
    }
    if (section) section.hidden = !(TRENDPICK_AFFILIATE.enabled || DEAL_ROWS.length);
    renderCoupangSearch();
  }

  /* --------------------------- 글감 키트 (X · 네이버 블로그) --------------------------- */
  // X(@jilyannori) 금기선 — 건축·부동산·맘카페·숲체험·정치·사건조사는 X 탭에서 자동 제외
  var X_BLOCK_WORDS = [
    '건축', '설계', '입찰', '나라장터', '시공', '감리', '인테리어', '공모', '하우재',
    '부동산', '아파트', '전세', '매매', '청약', '임대', '집값', '재건축', '경매', '상가', '오피스텔',
    '분양', '주택', '월세', '공시가격', '재개발', '입주', '중개', '노른자',
    '맘카페', '육아', '유아', '초등', '어린이집', '유치원', '학부모', '보육', '급식', '돌봄',
    '숲체험', '숲놀이', '그로우스페이스',
    '대통령', '국회', '여당', '야당', '민주당', '국민의힘', '선거', '장관', '검찰', '재판', '탄핵',
    '이재명', '윤석열', '한동훈', '청와대', '대통령실', '李',
    '전쟁', '북한', '미사일', '사망', '시신', '살인', '성폭행', '성매수', '마약', '음주운전', '자살', '도박'
  ];
  var X_PREFER = ['AI', '인공지능', '챗GPT', '클로드', '제미나이', '앱', '핫딜', '할인', '유튜브',
    '맛집', '여행', '생활', '꿀팁', 'IT', '스마트폰', '노트북', '로봇', '자동화', '무료'];

  function hasWord(text, words) {
    var low = String(text || '').toLowerCase();
    for (var i = 0; i < words.length; i++) {
      if (low.indexOf(String(words[i]).toLowerCase()) >= 0) return true;
    }
    return false;
  }
  function xSafe(c) {
    return !hasWord([c.raw || c.title, c.source, c.section].join(' '), X_BLOCK_WORDS);
  }
  function cleanTitle(t) {
    var s = String(t || '').replace(/\s+/g, ' ').trim();
    if (s.length > 70) {
      var parts = s.split(/\s*[/•|]\s*/).filter(Boolean);
      if (parts.length > 1 && parts[0].length >= 12) s = parts[0];
      if (s.length > 92) s = s.slice(0, 90) + '…';
    }
    return s;
  }
  function xScore(c) {
    var s = c.hot || 40;
    if (hasWord(c.title, X_PREFER)) s += 22;
    if (c.cat === 'ai') s += 18;
    else if (c.cat === 'apps') s += 10;
    else if (c.cat === 'youtube') s += 8;
    return s;
  }
  function prettyDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
    if (!m) return iso || '';
    return Number(m[2]) + '월 ' + Number(m[3]) + '일';
  }
  function kitCandidates() {
    var pool = [];
    function push(title, source, url, cat, hot, section) {
      if (!title || !url) return;
      pool.push({ raw: String(title), title: cleanTitle(title), source: source || '', url: url,
        cat: cat || 'news', hot: hot || 40, section: section || '' });
    }
    FEED.forEach(function (f) { push(f.title, f.source, f.url, f.cat, f.hot, f.section); });
    (((DATA.brief || {}).sections) || []).forEach(function (s) {
      (s.points || []).forEach(function (p) {
        var text = typeof p === 'string' ? p : p.text;
        var url = typeof p === 'string' ? '' : p.url;
        push(text, (typeof p === 'string' ? s.label : p.source), url, 'news', 38, s.label);
      });
    });
    var seen = {}, out = [];
    pool.forEach(function (c) {
      if (!xSafe(c)) return;
      var key = c.title.slice(0, 36).replace(/\s+/g, '');      if (seen[key]) return;
      seen[key] = 1;
      out.push(c);
    });
    out.sort(function (a, b) { return xScore(b) - xScore(a); });
    return out;
  }
  function topicPick(cat) {
    var sec = (((DATA.brief || {}).sections) || []).filter(function (s) { return s.key === cat; })[0];
    if (sec) {
      var p = (sec.points || [])[0];
      if (p) return {
        title: typeof p === 'string' ? p : p.text,
        url: typeof p === 'string' ? '' : p.url,
        source: typeof p === 'string' ? sec.label : (p.source || sec.label)
      };
    }
    var it = FEED.filter(function (f) { return f.cats.indexOf(cat) >= 0; })[0];
    return it ? { title: it.title, url: it.url, source: it.source } : null;
  }
  function shareIntent(text) {
    return 'https://twitter.com/intent/tweet?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(SITE_URL);
  }
  var KIT_CACHE = null;
  function buildKit() {
    if (KIT_CACHE) return KIT_CACHE;
    var b = DATA.brief || {};
    var date = prettyDate(b.date || (DATA.issue && DATA.issue.date) || '');
    var briefPicks = (b.picks || []).slice(0, 3).map(function (p) {
      return { title: p.title || '', source: p.source || '', url: p.url || '' };
    });
    var picks = kitCandidates().slice(0, 5);
    var topKw = (((DATA.ranks || {}).all) || [])[0];
    var kw = topKw ? topKw.k : '오늘의 트렌드';
    var items = (b.metrics && b.metrics.items) || (DATA.stats && DATA.stats.collected) || 0;

    /* 1) X 스레드 뼈대 — 금기선 제외·출처 URL·저장 유도 질문 */
    var x = [date + ' 아침에 훑어볼 만한 것만 ' + picks.length + '개 골랐어 👀', ''];
    picks.forEach(function (p, i) {
      x.push((i + 1) + '. ' + p.title);
      if (p.source) x.push('   ' + p.source);
      x.push('   ' + p.url);
      x.push('');
    });
    x.push('이 중에 뭐가 제일 궁금해? 저장해두고 저녁에 다시 보면 좋아.');
    x.push('매일 07:17 / 19:17 업데이트 · 트렌드픽 ' + SITE_URL);

    /* 2) 네이버 블로그 초안 — 목차 없이 핵심 3줄 요약 + 소제목 3개 + 유입 링크 */
    var lead = (briefPicks[0] && briefPicks[0].title ? briefPicks[0] : picks[0]) ||
      { title: kw, source: '트렌드픽', url: SITE_URL };
    var sum = (briefPicks.length ? briefPicks : picks).slice(0, 3).map(function (p) {
      return '> · ' + String(p.title).slice(0, 70);
    });
    while (sum.length < 3) sum.push('> · ' + kw);
    var ai = topicPick('ai');
    var app = topicPick('apptech');
    var blogLines = [];
    blogLines.push('제목: ' + date + ' 3분 브리프 — 오늘 제일 뜬 건 \'' + kw + '\'');
    blogLines.push('');
    blogLines.push('> 핵심 3줄 요약');
    blogLines.push(sum.join('\n'));
    blogLines.push('');
    blogLines.push(date + ' 트렌드픽이 공개 RSS·API에서 모은 ' + (items || '오늘') + '건 중에서 많이 읽힌 것부터 정리했습니다.');
    blogLines.push('');
    blogLines.push('◆ 오늘 제일 많이 본 이야기');
    blogLines.push(lead.title);
    blogLines.push((lead.source ? lead.source + '에서 전한 소식입니다. ' : '') +
      '원문에서 전체 내용을 확인하고, 아래 트렌드픽에서 오늘 흐름을 한 번에 볼 수 있습니다.');
    if (lead.url) blogLines.push('원문: ' + lead.url);
    blogLines.push('');
    blogLines.push('◆ AI·부업에서 눈에 띈 것');
    if (ai) {
      blogLines.push(ai.title);
      blogLines.push((ai.source ? ai.source + ' · ' : '') + (ai.url || ''));
    } else {
      blogLines.push('오늘은 AI·부업 쪽에서 새로 눈에 띈 소식이 적었습니다. 다음 수집에서 다시 채워집니다.');
    }
    blogLines.push('');
    blogLines.push('◆ 지금 챙겨볼 할인·앱테크');
    if (app) {
      blogLines.push(app.title);
      blogLines.push((app.source ? app.source + ' · ' : '') + (app.url || ''));
    } else {
      blogLines.push('오늘은 새로 올라온 할인 소식이 적었습니다. 트렌드픽 \'특가·핫딜\'에서 쿠팡 최저가를 바로 비교할 수 있습니다.');
    }
    blogLines.push('');
    blogLines.push('오늘 브리프 전체는 여기서 3분이면 다 볼 수 있어요.');
    blogLines.push('→ ' + SITE_URL);
    blogLines.push('매일 07:17 / 19:17 자동 업데이트');

    /* 3) 공유 문구 */
    var share = '오늘 뜬 이야기, 3분이면 다 볼 수 있게 정리했어 👀\n' +
      (picks[0] ? picks[0].title + '\n' : '') + SITE_URL;

    KIT_CACHE = {
      x: x.join('\n'),
      blog: blogLines.join('\n'),
      share: share,
      intent: shareIntent('오늘 뜬 이야기, 3분이면 다 볼 수 있게 정리했어 👀')
    };
    return KIT_CACHE;
  }

  var kitTab = 'x';
  function kitModal() {
    var kit = buildKit();
    kitTab = 'x';
    openModal({
      eyebrow: 'CREATOR KIT · ' + ((DATA.brief && DATA.brief.date) || ''),
      title: '✨ X·블로그 글감 키트',
      body: '<div class="kit-tabs" role="tablist" aria-label="글감 종류">' +
        '<button class="kit-tab" type="button" role="tab" data-kit="x" aria-selected="true" data-testid="kit-tab-x">X 스레드 뼈대</button>' +
        '<button class="kit-tab" type="button" role="tab" data-kit="blog" aria-selected="false" data-testid="kit-tab-blog">네이버 블로그 초안</button>' +
        '<button class="kit-tab" type="button" role="tab" data-kit="share" aria-selected="false" data-testid="kit-tab-share">공유 문구</button>' +
        '</div>' +
        '<div class="kit-pane" data-pane="x"><pre id="kitTextX" data-testid="kit-text-x">' + esc(kit.x) + '</pre></div>' +
        '<div class="kit-pane" data-pane="blog" hidden><pre id="kitTextBlog" data-testid="kit-text-blog">' + esc(kit.blog) + '</pre></div>' +
        '<div class="kit-pane" data-pane="share" hidden><pre id="kitTextShare" data-testid="kit-text-share">' + esc(kit.share) + '</pre></div>' +
        '<p class="kit-hint"><b>X</b> 는 금기선(건축·부동산·맘카페·숲체험·정치) 단어를 걸러낸 IT/AI·생활·앱 소재만 담았어요. ' +
        '<b>블로그</b>는 목차 없이 핵심 3줄 요약으로 시작하고, 트렌드픽 유입 링크가 들어갑니다.</p>',
      foot: '<button class="btn btn-ink" type="button" id="kitCopy" data-testid="kit-copy">📋 현재 글감 복사</button>' +
        '<a class="btn btn-line" id="kitShare" href="' + esc(kit.intent) + '" target="_blank" rel="noopener" data-testid="kit-share">X에 트렌드픽 공유</a>' +
        '<button class="btn" type="button" data-close>닫기</button>' +
        '<span style="flex:1"></span><span class="micro">07:17 / 19:17 자동 갱신</span>'
    });
    function activeText() {
      return kitTab === 'x' ? kit.x : kitTab === 'blog' ? kit.blog : kit.share;
    }
    $$('#mBody [data-kit]').forEach(function (t) {
      t.addEventListener('click', function () {
        kitTab = t.getAttribute('data-kit');
        $$('#mBody [data-kit]').forEach(function (x) { x.setAttribute('aria-selected', String(x === t)); });
        $$('#mBody .kit-pane').forEach(function (p) { p.hidden = p.getAttribute('data-pane') !== kitTab; });
      });
    });
    var cp = $('#kitCopy');
    if (cp) cp.addEventListener('click', function () {
      copyText(activeText(), '글감을 복사했습니다 · X나 블로그에 붙여넣기만 하면 돼요');
    });
  }

  function itemSnippet(f) {
    var label = CAT[f.cat] ? CAT[f.cat].label : '소식';
    var lines = ['[' + label + '] ' + f.title];
    if (f.source) lines.push('출처: ' + f.source + (f.time ? ' · ' + f.time : ''));
    if (f.url) lines.push('원문: ' + f.url);
    lines.push('');
    lines.push('한 줄: ' + String(f.title).slice(0, 60) + ' — 이거 어떻게 생각해?');
    lines.push('오늘 브리프 더 보기 → ' + SITE_URL);
    return lines.join('\n');
  }

  /* --------------------------- 오픈소스 · 앱 · 해커톤 --------------------------- */
  function renderOpensource() {
    var list = DATA.opensource || [];
    $('#osList').innerHTML = list.length ? list.slice(0, 6).map(function (o, i) {
      return '<a class="os-item" href="' + esc(o.url || '#') + '" target="_blank" rel="noopener" data-testid="os-' + i + '">' +
        '<span class="os-ico">' + artSvg('os', o.repo) +
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
        '<span class="ap-ico">' + artSvg('apps', a.name) +
          (a.img ? '<img src="' + esc(a.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer" decoding="async">' : '') +
        '</span><span class="ap-body"><span class="ap-n">' + esc(a.name) + '</span>' +
        '<span class="ap-c">' + esc(a.category || '') + '</span></span></a>';
    }).join('') : '<div class="empty"><b>순위를 가져오지 못했습니다</b>앱스토어·스팀 응답을 확인하세요.</div>';
  }

  function renderHackathons() {
    var list = DATA.hackathons || [];
    $('#hackList').innerHTML = list.length ? list.slice(0, 6).map(function (h, i) {
      return '<a class="hack" href="' + esc(h.url || '#') + '" target="_blank" rel="noopener" data-testid="hack-' + i + '">' +
        '<span class="hack-thumb">' + artSvg('hack', h.name) +
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
    var qClear = $('#qClear');
    q.addEventListener('input', function () {
      state.q = q.value; state.kw = ''; state.limit = 12;
      syncSearchChip();
      renderFeed();
    });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); clearSearch(true); }
    });

    // 검색 실행 — 버튼 클릭 또는 Enter(submit)에서만 키보드를 닫고 결과로 이동합니다.
    function runSearch() {
      var term = (q.value || '').trim();
      if (!term) { q.focus(); toast('찾고 싶은 키워드를 적어 주세요'); return; }
      state.q = term; state.kw = ''; state.limit = 12;
      renderFeed(); syncSearchChip();
      try { q.blur(); } catch (err) {}          // 모바일 가상 키보드 닫기
      scrollToResults();
      var n = visibleList().length;
      toast(n ? '‘' + term + '’ 검색 결과 ' + n + '건' : '‘' + term + '’에 맞는 픽이 없습니다');
    }
    var searchForm = $('#searchWrap');
    if (searchForm) searchForm.addEventListener('submit', function (e) { e.preventDefault(); runSearch(); });
    qClear.addEventListener('click', function () { clearSearch(true); });
    if ($('#qChip')) $('#qChip').addEventListener('click', function () { clearSearch(false); });

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

    // 저장 · 글감 복사
    $('#feedGrid').addEventListener('click', function (e) {
      var c = e.target.closest('[data-copy]');
      if (c) {
        e.preventDefault(); e.stopPropagation();
        var item = itemById(c.getAttribute('data-copy'));
        if (item) copyText(itemSnippet(item), '글감을 복사했습니다 · 바로 붙여넣어 쓰세요');
        return;
      }
      var b = e.target.closest('[data-save]');
      if (!b) return;
      e.preventDefault(); e.stopPropagation();
      toggleSaved(b.getAttribute('data-save'));
    });
    // 핫딜 글감 복사
    $('#dealGrid').addEventListener('click', function (e) {
      var b = e.target.closest('[data-deal-copy]');
      if (!b) return;
      e.preventDefault(); e.stopPropagation();
      var d = DEAL_ROWS[Number(b.getAttribute('data-deal-copy'))];
      if (d) copyText(dealCopyText(d), '핫딜 글감을 복사했습니다');
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
    $('#bOpen').addEventListener('click', function () {
      var deep = document.getElementById('brief-deep');
      if (deep) deep.scrollIntoView({ behavior: 'smooth', block: 'start' });
      else briefModal();
    });
    $('#bKit').addEventListener('click', kitModal);
    $('#bPast').addEventListener('click', pastModal);
    $('#brief').addEventListener('click', function (e) {
      if (e.target.closest('#bOpen') || e.target.closest('#bKit') || e.target.closest('#bPast') || e.target.closest('a')) return;
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
          KIT_CACHE = null;          // 새 수집 데이터로 글감 키트를 다시 조합합니다
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
