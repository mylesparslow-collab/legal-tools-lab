/* Catch-the-error drill: trainee app. Needs data.js and scoring.js loaded first. */
(function () {
  'use strict';

  var DATA = window.DRILL_DATA;
  var S = window.DrillScoring;
  var RULE = DATA.rule;
  var main = document.getElementById('main');
  var live = document.getElementById('live');
  var STORE_KEY = 'catch-the-error-drill:last-result';

  var DOCS = {};
  DATA.docs.forEach(function (d) { DOCS[d.id] = d; });
  var TYPES = {};
  DATA.types.forEach(function (t) { TYPES[t.id] = t.label; });

  var MODES = {
    review: 'Review an AI draft',
    spot: 'Timed spot check',
    verify: 'Which would you verify?'
  };

  // ------------------------------------------------------------ helpers

  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) { return; }
        if (k === 'class') { el.className = v; }
        else if (k === 'text') { el.textContent = v; }
        else if (k.slice(0, 2) === 'on') { el.addEventListener(k.slice(2), v); }
        else { el.setAttribute(k, v === true ? '' : v); }
      });
    }
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c === null || c === undefined || c === false) { continue; }
      if (Array.isArray(c)) { c.forEach(function (x) { if (x) { el.appendChild(x.nodeType ? x : document.createTextNode(x)); } }); }
      else { el.appendChild(c.nodeType ? c : document.createTextNode(String(c))); }
    }
    return el;
  }

  function say(msg) { live.textContent = ''; setTimeout(function () { live.textContent = msg; }, 30); }

  // Storage is optional. Every call is wrapped; the app works with storage blocked.
  var store = {
    get: function () { try { var v = window.localStorage.getItem(STORE_KEY); return v ? JSON.parse(v) : null; } catch (e) { return null; } },
    set: function (obj) { try { window.localStorage.setItem(STORE_KEY, JSON.stringify(obj)); return true; } catch (e) { return false; } }
  };

  function docText(doc) {
    if (!doc._text) { doc._text = doc.blocks.map(function (b) { return b.x; }).join('\n'); }
    return doc._text;
  }
  function slice(doc, s, e) { return docText(doc).slice(s, e); }
  function clip(str, n) { return str.length > n ? str.slice(0, n - 1).trimEnd() + '…' : str; }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function mmss(sec) { sec = Math.max(0, Math.ceil(sec)); return Math.floor(sec / 60) + ':' + ('0' + (sec % 60)).slice(-2); }
  function blockIndexAt(doc, offset) {
    var lo = 0, hi = doc.blocks.length - 1;
    while (lo < hi) { var mid = (lo + hi + 1) >> 1; if (doc.blocks[mid].s <= offset) { lo = mid; } else { hi = mid - 1; } }
    return lo;
  }
  function param(name) {
    try { return new URLSearchParams(window.location.search).get(name); } catch (e) { return null; }
  }

  // Rough sentences inside a block, as [start, end) local offsets. Short
  // fragments are joined to what follows so a keyboard target is never too
  // short to mark.
  function sentencesOf(text) {
    var out = [], start = 0, re = /(?<=[.;])\s+(?=[A-Z("“])/g, m;
    while ((m = re.exec(text)) !== null) {
      if (m.index - start >= RULE.minMarkChars) { out.push([start, m.index]); start = m.index + m[0].length; }
    }
    if (out.length && text.length - start < RULE.minMarkChars) { out[out.length - 1][1] = text.length; }
    else { out.push([start, text.length]); }
    return out;
  }

  // ------------------------------------------------------------ state

  var session = null;   // {set, exercises: [...], idx, results: [...]}
  var cur = null;       // the exercise in progress
  var timer = null;

  function stopTimer() { if (timer) { clearInterval(timer); timer = null; } }

  function show(viewClass, nodes, focusEl) {
    stopTimer();
    document.body.className = viewClass || '';
    main.textContent = '';
    nodes.forEach(function (n) { if (n) { main.appendChild(n); } });
    window.scrollTo(0, 0);
    var target = focusEl || main.querySelector('h1');
    if (target) { target.setAttribute('tabindex', '-1'); target.focus({ preventScroll: true }); }
  }

  // The part of a document an exercise shows, and the defects inside it.
  function scopeOf(ex) {
    var doc = DOCS[ex.doc];
    var from = 0, to = Infinity, excerpt = null;
    if (ex.excerpt) { excerpt = doc.excerpts[ex.excerpt]; from = excerpt.from; to = excerpt.to; }
    function inView(sec) { return sec === 0 || (sec >= from && sec <= to); }
    var blocks = [];
    doc.blocks.forEach(function (b, i) { if (inView(b.sec)) { blocks.push(i); } });
    var defects = doc.defects.filter(function (d) {
      return d.spans.every(function (sp) { return inView(doc.blocks[blockIndexAt(doc, sp[0])].sec); });
    });
    return { doc: doc, excerpt: excerpt, blocks: blocks, defects: defects,
             unscored: ex.excerpt ? [] : doc.unscored, inView: inView,
             words: ex.excerpt ? excerpt.words : doc.words };
  }

  // ------------------------------------------------------------ document rendering

  /*
   * Render blocks into `container`. opts:
   *   marks     [{id, start, end}] the trainee's marks
   *   planted   [{start, end, status}] planted spans, on the reveal screen only
   *   target    {block, start, end} keyboard target (global offsets)
   *   focusable true on the drill screen (roving tabindex on text blocks)
   * Returns {els: {blockIndex: element}, paint(blockIndex)}.
   */
  function renderDocument(container, scope, opts) {
    var doc = scope.doc, els = {}, table = null, tbody = null, row = null, rowNo = null, lastSec = 0, first = true;

    function paint(i) {
      var b = doc.blocks[i], el = els[i];
      if (!el) { return; }
      var len = b.x.length, bs = b.s, be = b.s + len;
      var cuts = [0, len];
      function cut(s, e) { if (s < be && e > bs) { cuts.push(Math.max(0, s - bs), Math.min(len, e - bs)); } }
      (b.b || []).forEach(function (r) { cuts.push(r[0], r[1]); });
      (opts.marks || []).forEach(function (m) { cut(m.start, m.end); });
      (opts.planted || []).forEach(function (p) { cut(p.start, p.end); });
      if (opts.target && opts.target.block === i) { cut(opts.target.start, opts.target.end); }
      cuts = cuts.filter(function (v, k, a) { return a.indexOf(v) === k; }).sort(function (a, b2) { return a - b2; });
      el.textContent = '';
      for (var k = 0; k < cuts.length - 1; k++) {
        var a = cuts[k], z = cuts[k + 1], ga = bs + a, gz = bs + z;
        var node = document.createTextNode(b.x.slice(a, z));
        if ((b.b || []).some(function (r) { return r[0] <= a && z <= r[1]; })) { node = h('strong', null, node); }
        if (opts.target && opts.target.block === i && opts.target.start <= ga && gz <= opts.target.end && opts.target.partial) {
          node = h('span', { class: 'kt' }, node);
        }
        var um = (opts.marks || []).filter(function (m) { return m.start <= ga && gz <= m.end; })[0];
        if (um) { node = h('mark', { class: 'um', 'data-mark': um.id }, node); }
        var pl = (opts.planted || []).filter(function (p) { return p.start <= ga && gz <= p.end; })[0];
        if (pl) {
          var wrap = h('mark', { class: 'pl ' + pl.status, 'data-defect': pl.id });
          if (pl.start === ga) {
            wrap.appendChild(h('span', { class: 'tag ' + pl.status, text: pl.status === 'missed' ? 'Missed' : 'Found' }));
          }
          wrap.appendChild(node);
          node = wrap;
        }
        el.appendChild(node);
      }
    }

    scope.blocks.forEach(function (i) {
      var b = doc.blocks[i], el;
      if (scope.excerpt && b.sec !== 0 && lastSec === 0) {
        container.appendChild(h('p', { class: 'gap', text: b.sec > 1
          ? 'Sections before this point are left out of the exercise.'
          : 'The exercise covers the sections that follow.' }));
      }
      lastSec = b.sec;
      if (b.t === 'th' || b.t === 'td') {
        if (!table) {
          tbody = h('tbody');
          table = h('table', null, tbody);
          container.appendChild(h('div', { class: 'tablewrap' }, table));
          rowNo = null;
        }
        if (b.r !== rowNo) { row = h('tr'); tbody.appendChild(row); rowNo = b.r; }
        el = h(b.t, b.t === 'th' ? { scope: 'col' } : null);
        row.appendChild(el);
      } else {
        table = null;
        if (b.t === 'hr') { container.appendChild(h('hr')); return; }
        if (b.t === 'h1') { el = h('h2', { class: 'd1' }); }
        else if (b.t === 'h2') { el = h('h3', { class: 'd2' }); }
        else if (b.t === 'h3') { el = h('h4', { class: 'd3' }); }
        else { el = h('p', { class: (b.c ? 'c ' : '') + (b.i ? 'i' : '') || null }); }
        container.appendChild(el);
      }
      el.classList.add('blk');
      el.setAttribute('data-b', i);
      if (opts.focusable && b.x.length) { el.setAttribute('tabindex', first ? '0' : '-1'); first = false; }
      els[i] = el;
      paint(i);
    });
    if (scope.excerpt) {
      container.appendChild(h('p', { class: 'gap', text: 'The rest of the agreement is left out of the exercise.' }));
    }
    return { els: els, paint: paint };
  }

  // Selection in the document -> [start, end) display offsets, or null.
  function selectionSpan(container, doc) {
    var sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) { return null; }
    var range = sel.getRangeAt(0);
    if (!container.contains(range.commonAncestorContainer) && range.commonAncestorContainer !== container) { return null; }
    var start = null, end = null;
    var blks = container.querySelectorAll('.blk');
    for (var k = 0; k < blks.length; k++) {
      var el = blks[k];
      if (!range.intersectsNode(el)) { continue; }
      var b = doc.blocks[+el.getAttribute('data-b')];
      var r = document.createRange();
      r.selectNodeContents(el);
      var a = 0, z = b.x.length;
      if (el.contains(range.startContainer)) { r.setEnd(range.startContainer, range.startOffset); a = r.toString().length; }
      r.selectNodeContents(el);
      if (el.contains(range.endContainer)) { r.setEnd(range.endContainer, range.endOffset); z = r.toString().length; }
      if (z <= a) { continue; }
      if (start === null) { start = b.s + a; }
      end = b.s + z;
    }
    if (start === null) { return null; }
    return trimSpan(doc, start, end);
  }

  function trimSpan(doc, start, end) {
    var t = docText(doc);
    while (start < end && /\s/.test(t[start])) { start++; }
    while (end > start && /\s/.test(t[end - 1])) { end--; }
    return end > start ? [start, end] : null;
  }

  // ------------------------------------------------------------ home

  function viewHome() {
    session = null; cur = null;
    var areas = [];
    DATA.sets.forEach(function (s) { if (areas.indexOf(s.area) < 0) { areas.push(s.area); } });
    var choice = { area: areas[0], length: 20, rotation: 'A' };
    var plan = h('div', { class: 'plan', id: 'plan', 'aria-live': 'polite' });

    function currentSet() {
      return DATA.sets.filter(function (s) {
        return s.area === choice.area && s.length === choice.length && s.rotation === choice.rotation;
      })[0];
    }
    function drawPlan() {
      var set = currentSet(), total = 0;
      plan.textContent = '';
      plan.appendChild(h('h3', { text: 'This session' }));
      plan.appendChild(h('ol', null, set.exercises.map(function (ex) {
        total += ex.minutes;
        return h('li', null, exerciseLabel(ex) + ', ' + plural(ex.minutes, 'minute', 'minutes') + '. ',
          h('span', { class: 'muted', text: DOCS[ex.doc].title }));
      })));
      plan.appendChild(h('p', { class: 'small muted', text: 'About ' + total + ' minutes of exercises. The rest of the ' +
        set.length + ' minutes is for reading the answers after each one.' }));
    }
    function radios(name, legend, options, key, row) {
      return h('fieldset', null, h('legend', { text: legend }),
        h('div', { class: 'choices' + (row ? ' row' : '') }, options.map(function (o) {
          var input = h('input', { type: 'radio', name: name, value: String(o.value), checked: choice[key] === o.value,
            onchange: function () { choice[key] = o.value; drawPlan(); } });
          return h('label', null, input, h('span', { text: o.label }));
        })));
    }

    var single = { mode: 'review', doc: DATA.docs[0].id };
    var last = store.get();
    drawPlan();
    show('', [h('div', { class: 'page' },
      h('h1', { text: 'Catch-the-error drill' }),
      h('p', { class: 'lede', text: 'A reading exercise. You review contract drafts that have errors planted in them, then see what you caught and what you missed.' }),
      h('div', { class: 'note' },
        h('p', { text: 'Personal portfolio demo. Every document here is fictional and was written to carry planted errors. Nothing here is legal advice, and none of it was reviewed by an attorney.' }),
        h('p', { text: 'Nothing you do on this page leaves your device.' })),
      h('h2', { text: 'Set up a session' }),
      radios('area', 'Practice area', areas.map(function (a) {
        return { value: a, label: a === 'Mixed' ? 'Mixed (one document from each of three areas)' : a };
      }), 'area'),
      radios('length', 'Length', [10, 20, 30].map(function (n) { return { value: n, label: n + ' minutes' }; }), 'length', true),
      radios('rotation', 'Rotation', ['A', 'B', 'C'].map(function (r) { return { value: r, label: 'Rotation ' + r }; }), 'rotation', true),
      h('p', { class: 'small muted', text: 'Each rotation uses the same documents in different exercises. Pick another rotation for a group that has done this area before.' }),
      plan,
      h('div', { class: 'actions' },
        h('button', { class: 'primary', id: 'start-session', onclick: function () { startSession(currentSet()); } }, 'Start session')),
      h('details', { id: 'single' },
        h('summary', { text: 'Or run a single exercise' }),
        h('p', null, h('label', { for: 'single-mode', text: 'Exercise ' }),
          h('select', { id: 'single-mode', onchange: function (e) { single.mode = e.target.value; } },
            Object.keys(MODES).map(function (m) { return h('option', { value: m, text: MODES[m] + (m === 'review' ? ' (whole document)' : '') }); }))),
        h('p', null, h('label', { for: 'single-doc', text: 'Document ' }),
          h('select', { id: 'single-doc', onchange: function (e) { single.doc = e.target.value; } },
            DATA.docs.map(function (d) { return h('option', { value: d.id, text: d.id + ': ' + clip(d.title, 70) }); }))),
        h('div', { class: 'actions' }, h('button', { id: 'start-single', onclick: function () {
          var ex = { mode: single.mode, doc: single.doc };
          if (ex.mode === 'spot') { ex.seconds = DATA.assumptions.spotSeconds; ex.minutes = ex.seconds / 60; }
          startSession({ id: 'single-' + ex.mode + '-' + ex.doc, area: DOCS[ex.doc].area, length: null, rotation: null, exercises: [ex] });
        } }, 'Start exercise'))),
      last ? h('p', null, h('button', { class: 'link', id: 'reopen', onclick: function () { viewSummary(last, true); } },
        'Open the summary of the last session on this device')) : null
    )]);
  }

  function exerciseLabel(ex) {
    return MODES[ex.mode] + (ex.excerpt ? ' (excerpt)' : '');
  }

  function startSession(set) {
    session = { set: set, exercises: set.exercises, idx: 0, results: [], id: randomId() };
    viewIntro();
  }

  function randomId() {
    var s = '';
    try {
      var a = new Uint8Array(6);
      window.crypto.getRandomValues(a);
      for (var i = 0; i < a.length; i++) { s += ('0' + a[i].toString(16)).slice(-2); }
    } catch (e) { s = Math.floor(Math.random() * 1e12).toString(16); }
    return s;
  }

  // ------------------------------------------------------------ intro

  function spotSeconds(ex) {
    var q = parseInt(param('seconds'), 10);
    return q > 0 ? q : ex.seconds;
  }

  function markingHelp() {
    return h('ul', null,
      h('li', { text: 'Mouse or touch: select the words, then choose a type in the marking panel.' }),
      h('li', null, 'Keyboard: press ', h('kbd', { text: 'Tab' }), ' to reach the draft. ', h('kbd', { text: '↑' }), ' and ',
        h('kbd', { text: '↓' }), ' move between paragraphs. ', h('kbd', { text: '←' }), ' and ', h('kbd', { text: '→' }),
        ' pick one sentence. Press ', h('kbd', { text: '1' }), ', ', h('kbd', { text: '2' }), ' or ', h('kbd', { text: '3' }), ' to mark it.'),
      h('li', { text: 'A mark must be between ' + RULE.minMarkChars + ' and ' + RULE.maxMarkChars + ' characters. Mark the sentence that is wrong, not the whole page.' }),
      h('li', { text: 'One mark counts for one error.' }));
  }

  function viewIntro() {
    var ex = session.exercises[session.idx];
    var scope = scopeOf(ex);
    var body = [];
    var count = session.exercises.length > 1 ? 'Exercise ' + (session.idx + 1) + ' of ' + session.exercises.length : null;
    if (ex.mode === 'verify') {
      body.push(h('p', { text: 'These ' + scope.doc.verify.length + ' statements were taken from an AI-assisted draft of the agreement named below. Tick each one you would check against the source before relying on it.' }));
      body.push(h('p', { text: 'Suggested time: 3 minutes.' }));
    } else {
      body.push(h('p', { text: 'Treat this as an AI-assisted draft that has come to you for review. Mark each passage you think conflicts with a statute or regulation, and choose what kind of problem it is.' }));
      if (ex.mode === 'spot') {
        var sec = spotSeconds(ex);
        body.push(h('p', { text: 'You have ' + (sec % 60 === 0 ? plural(sec / 60, 'minute', 'minutes') : sec + ' seconds') +
          ' for the whole agreement, about ' + scope.words.toLocaleString('en-US') + ' words. The clock starts when you press Start. When it stops, the answers are shown.' }));
      } else {
        body.push(h('p', { text: (ex.excerpt
          ? 'This is an excerpt of about ' + scope.words.toLocaleString('en-US') + ' words. '
          : 'This is the whole agreement, about ' + scope.words.toLocaleString('en-US') + ' words. ') +
          'There is no time limit.' + (ex.minutes ? ' Suggested time: about ' + ex.minutes + ' minutes.' : '') }));
      }
      body.push(h('h2', { text: 'How to mark' }));
      body.push(markingHelp());
    }
    show('', [h('div', { class: 'page' },
      count ? h('p', { class: 'muted small', text: count }) : null,
      h('h1', { text: MODES[ex.mode] }),
      h('p', { class: 'muted', text: scope.doc.title }),
      body,
      h('div', { class: 'note' }, h('p', { text: 'The document is fictional. The errors in it were planted for this exercise.' })),
      h('div', { class: 'actions' },
        h('button', { class: 'primary', id: 'begin', onclick: function () { ex.mode === 'verify' ? viewVerify() : viewDrill(); } }, 'Start'),
        h('button', { onclick: viewHome }, 'Back to setup'))
    )]);
  }

  // ------------------------------------------------------------ marking drill

  function viewDrill() {
    var ex = session.exercises[session.idx];
    var scope = scopeOf(ex);
    var doc = scope.doc;
    var timed = ex.mode === 'spot';
    var total = timed ? spotSeconds(ex) : null;
    cur = { ex: ex, scope: scope, marks: [], seq: 0, started: Date.now(), locked: false,
            pending: null, target: null, keyboard: false };

    var docEl = h('article', { class: 'doc', id: 'doc', 'aria-label': 'Draft under review' });
    var view = { marks: cur.marks, target: null, focusable: true };
    var rendered = renderDocument(docEl, scope, view);

    var clock = h('div', { class: 'clock', id: 'clock', role: 'timer', text: timed ? mmss(total) : '0:00' });
    var pendingEl = h('p', { class: 'pending empty', id: 'pending', text: 'Nothing selected yet.' });
    var statusEl = h('p', { class: 'status', id: 'mark-status', role: 'status' });
    var listEl = h('ol', { class: 'marks', id: 'marks' });
    var listHead = h('summary', { id: 'marks-count', text: 'Your marks (0)' });
    var typeButtons = DATA.types.map(function (t, n) {
      return h('button', { type: 'button', 'data-type': t.id, disabled: true,
        onmousedown: function (e) { e.preventDefault(); },
        onclick: function () { addMark(t.id); } },
        h('span', { class: 'num', text: String(n + 1) }), h('span', { text: t.label }));
    });
    var wideScreen = !window.matchMedia || window.matchMedia('(min-width: 62.01rem)').matches;
    var panel = h('aside', { class: 'panel', 'aria-label': 'Marking panel' },
      h('section', { class: 'sec-clock' },
        h('div', { class: 'clock-label', text: timed ? 'Time left' : 'Time spent' }), clock,
        !timed && ex.minutes ? h('div', { class: 'clock-label', text: 'Suggested: ' + ex.minutes + ' min' }) : null),
      h('section', { class: 'sec-mark' },
        h('h2', { text: 'Mark the selected passage as' }),
        pendingEl,
        h('div', { class: 'types', role: 'group', 'aria-label': 'Defect type' }, typeButtons),
        statusEl),
      h('section', { class: 'sec-list' }, h('details', { open: wideScreen }, listHead, listEl)),
      h('section', { class: 'sec-help help' }, h('details', null, h('summary', { text: 'How to mark' }), markingHelp())),
      h('section', { class: 'sec-finish' },
        h('button', { class: 'primary finish', id: 'finish', onclick: function () { finishDrill(false); } }, 'Finish and see answers')));

    function setPending(span, fromKeyboard) {
      cur.pending = span ? { start: span[0], end: span[1], keyboard: !!fromKeyboard } : null;
      typeButtons.forEach(function (b) { b.disabled = !span || cur.locked; });
      if (!span) { pendingEl.className = 'pending empty'; pendingEl.textContent = 'Nothing selected yet.'; return; }
      pendingEl.className = 'pending';
      pendingEl.textContent = clip(slice(doc, span[0], span[1]), 150);
    }

    function setTarget(target) {
      var old = view.target;
      view.target = target;
      if (old && (!target || old.block !== target.block)) { rendered.paint(old.block); }
      if (target) { rendered.paint(target.block); }
    }

    function drawList() {
      listEl.textContent = '';
      listHead.textContent = 'Your marks (' + cur.marks.length + ')';
      if (!cur.marks.length) { listEl.appendChild(h('li', { class: 'muted', text: 'No marks yet.' })); }
      cur.marks.slice().sort(function (a, b) { return a.start - b.start; }).forEach(function (m) {
        listEl.appendChild(h('li', null,
          h('button', { class: 'link snip', title: 'Show in the draft', onclick: function () {
            var el = docEl.querySelector('[data-mark="' + m.id + '"]');
            if (el) { el.scrollIntoView({ block: 'center' }); }
          } }, '“' + clip(slice(doc, m.start, m.end), 90) + '”'),
          h('div', { class: 'row' }, h('span', { text: TYPES[m.type] }),
            h('button', { class: 'remove', 'aria-label': 'Remove mark: ' + clip(slice(doc, m.start, m.end), 40),
              onclick: function () { removeMark(m.id); } }, 'Remove'))));
      });
    }

    function repaint(start, end) {
      scope.blocks.forEach(function (i) {
        var b = doc.blocks[i];
        if (b.s < end && start < b.s + b.x.length) { rendered.paint(i); }
      });
    }

    function addMark(type) {
      if (cur.locked || !cur.pending) { return; }
      var p = cur.pending, len = p.end - p.start;
      if (len < RULE.minMarkChars) {
        statusEl.textContent = 'Too short to mark. Select at least ' + RULE.minMarkChars + ' characters.';
        return;
      }
      if (len > RULE.maxMarkChars) {
        statusEl.textContent = 'Too long to mark (' + len + ' characters, limit ' + RULE.maxMarkChars + '). Pick the sentence that is wrong.';
        return;
      }
      var same = cur.marks.filter(function (m) { return m.start === p.start && m.end === p.end; })[0];
      if (same) { same.type = type; statusEl.textContent = 'Type changed: ' + TYPES[type] + '.'; }
      else {
        cur.seq += 1;
        cur.marks.push({ id: 'm' + cur.seq, start: p.start, end: p.end, type: type });
        statusEl.textContent = 'Marked: ' + TYPES[type] + '.';
      }
      var sel = window.getSelection();
      var keep = p.keyboard ? document.activeElement : null;
      if (sel && !p.keyboard) { sel.removeAllRanges(); }
      repaint(p.start, p.end);
      if (!p.keyboard) { setPending(null); }
      if (keep && keep.focus) { keep.focus({ preventScroll: true }); }
      drawList();
    }

    function removeMark(id) {
      var k = cur.marks.map(function (m) { return m.id; }).indexOf(id);
      if (k < 0) { return; }
      var m = cur.marks.splice(k, 1)[0];
      repaint(m.start, m.end);
      drawList();
      statusEl.textContent = 'Mark removed.';
      listHead.focus();
    }

    // Mouse and touch: follow the browser's selection.
    cur.onSelection = function () {
      if (cur.locked) { return; }
      var span = selectionSpan(docEl, doc);
      if (span) { setTarget(null); setPending(span, false); statusEl.textContent = ''; }
      else if (cur.pending && !cur.pending.keyboard && !panel.contains(document.activeElement)) { setPending(null); }
    };
    document.addEventListener('selectionchange', cur.onSelection);
    docEl.addEventListener('pointerdown', function () { cur.keyboard = false; });

    // Keyboard: a roving tab stop over the paragraphs, sentence by sentence.
    function focusBlock(i) {
      var el = rendered.els[i];
      if (!el) { return; }
      var prev = docEl.querySelector('.blk[tabindex="0"]');
      if (prev) { prev.setAttribute('tabindex', '-1'); }
      el.setAttribute('tabindex', '0');
      el.focus();
    }
    function chooseTarget(i, sent) {
      var b = doc.blocks[i];
      var sents = sentencesOf(b.x);
      if (sent < -1) { sent = sents.length - 1; }
      if (sent >= sents.length) { sent = -1; }
      var loc = sent === -1 ? [0, b.x.length] : sents[sent];
      var span = trimSpan(doc, b.s + loc[0], b.s + loc[1]);
      if (!span) { return; }
      cur.target = { block: i, sent: sent, count: sents.length };
      setTarget({ block: i, start: span[0], end: span[1], partial: sent !== -1 });
      setPending(span, true);
      var what = sent === -1 ? 'Whole paragraph' : 'Sentence ' + (sent + 1) + ' of ' + sents.length;
      statusEl.textContent = what + ' selected, ' + (span[1] - span[0]) + ' characters.';
    }
    docEl.addEventListener('focusin', function (e) {
      var el = e.target.closest ? e.target.closest('.blk') : null;
      if (!el || !cur.keyboard || cur.locked) { return; }
      chooseTarget(+el.getAttribute('data-b'), -1);
    });
    docEl.addEventListener('keydown', function (e) {
      var el = e.target.closest ? e.target.closest('.blk') : null;
      if (!el || e.altKey || e.ctrlKey || e.metaKey) { return; }
      var i = +el.getAttribute('data-b');
      var order = scope.blocks.filter(function (k) { return doc.blocks[k].x.length && rendered.els[k]; });
      var at = order.indexOf(i);
      cur.keyboard = true;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        var next = order[at + (e.key === 'ArrowDown' ? 1 : -1)];
        if (next !== undefined) { focusBlock(next); }
        e.preventDefault();
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        var s = cur.target && cur.target.block === i ? cur.target.sent : -1;
        chooseTarget(i, s + (e.key === 'ArrowRight' ? 1 : -1));
        e.preventDefault();
      } else if (e.key === 'Escape') {
        chooseTarget(i, -1);
      } else if (/^[1-9]$/.test(e.key) && DATA.types[+e.key - 1]) {
        if (!cur.pending || !cur.pending.keyboard || !cur.target || cur.target.block !== i) { chooseTarget(i, -1); }
        addMark(DATA.types[+e.key - 1].id);
        e.preventDefault();
      }
    });
    docEl.addEventListener('keyup', function (e) { if (e.key === 'Tab') { cur.keyboard = true; } });
    document.addEventListener('keydown', cur.onTab = function (e) { if (e.key === 'Tab') { cur.keyboard = true; } });

    function finishDrill(timeUp) {
      if (cur.locked) { return; }
      cur.locked = true;
      document.removeEventListener('selectionchange', cur.onSelection);
      document.removeEventListener('keydown', cur.onTab);
      var used = Math.round((Date.now() - cur.started) / 1000);
      var score = S.scoreMarks(scope.defects, cur.marks, RULE);
      var result = { mode: ex.mode, doc: doc.id, docSha256: doc.sha256, excerpt: ex.excerpt || null,
        secondsUsed: timed ? Math.min(used, total) : used, secondsAllowed: total, timeUp: !!timeUp, score: score };
      session.results.push(result);
      viewReveal(result);
    }

    drawList();
    show('drill-view', [
      h('div', { class: 'drill-head' },
        h('h1', { text: MODES[ex.mode] + (ex.excerpt ? ', excerpt' : '') }),
        h('p', { class: 'muted small', text: 'AI-assisted draft for review. Fictional document with planted errors.' })),
      h('div', { class: 'drill' }, docEl, panel)
    ]);

    timer = setInterval(function () {
      var elapsed = (Date.now() - cur.started) / 1000;
      if (!timed) { clock.textContent = mmss(Math.floor(elapsed)); return; }
      var left = total - elapsed;
      clock.textContent = mmss(left);
      if (left <= 60 && !cur.warned && total > 60) { cur.warned = true; clock.classList.add('low'); say('One minute left.'); }
      if (left <= 0) { say('Time is up.'); finishDrill(true); }
    }, 250);
  }

  // ------------------------------------------------------------ reveal (marking modes)

  function defectCard(doc, d, status, extra) {
    var label = status === 'found' ? 'Found' : status === 'misclassified' ? 'Found, misclassified' : status === 'missed' ? 'Missed' : 'Not scored';
    return h('div', { class: 'card ' + (status === 'missed' ? 'missed' : status === 'unscored' ? '' : 'found'), 'data-defect': d.id, 'data-status': status },
      h('h3', { text: d.title }),
      d.spans.map(function (sp) { return h('blockquote', { text: slice(doc, sp[0], sp[1]) }); }),
      h('p', { class: 'meta', text: label + '. Catalog type: ' + TYPES[d.type] + '.' }),
      extra || null,
      h('p', { text: d.why }),
      h('p', { class: 'meta', text: d.authority }),
      h('details', null,
        h('summary', { text: 'The rule, as read for the catalog' }),
        h('p', { text: DATA.catalog[d.code].rule }),
        h('p', { class: 'meta', text: d.read.map(function (r) {
          return r.section + ', read ' + r.date + ' (' + r.source + ')' + (r.note ? '. ' + r.note : '');
        }).join(' ') })));
  }

  function scoreItem(n, label, key) {
    return h('li', null, h('span', { class: 'n', 'data-count': key, text: String(n) }), h('span', { class: 'l', text: label }));
  }

  function nextActions() {
    var lastOne = session.idx >= session.exercises.length - 1;
    return h('div', { class: 'actions' },
      h('button', { class: 'primary', id: 'next', onclick: function () {
        if (lastOne) { viewSummary(buildResult(), false); } else { session.idx += 1; viewIntro(); }
      } }, lastOne ? 'Go to the session summary' : 'Next exercise'));
  }

  function viewReveal(result) {
    var ex = session.exercises[session.idx];
    var scope = scopeOf(ex), doc = scope.doc, score = result.score, c = score.counts;
    var marksById = {}, defectsById = {};
    cur.marks.forEach(function (m) { marksById[m.id] = m; });
    scope.defects.forEach(function (d) { defectsById[d.id] = d; });

    var found = h('section', { class: 'col-found', 'aria-labelledby': 'h-found' }, h('h2', { id: 'h-found', text: 'Found (' + c.found + ')' }));
    var missed = h('section', { class: 'col-missed', 'aria-labelledby': 'h-missed' }, h('h2', { id: 'h-missed', text: 'Missed (' + c.missed + ')' }));
    var falseCol = h('section', { class: 'col-false', 'aria-labelledby': 'h-false' }, h('h2', { id: 'h-false', text: 'False alarms (' + c.falseAlarms + ')' }));

    score.defects.forEach(function (row) {
      var d = defectsById[row.id], extra = [];
      if (row.status === 'misclassified') {
        extra.push(h('p', { text: 'You marked the right place and chose “' + TYPES[row.chosenType] + '”.' }));
      }
      if (row.markIds.length > 1) { extra.push(h('p', { class: 'meta', text: 'You marked this ' + row.markIds.length + ' times. It counts once.' })); }
      var also = score.marks.filter(function (m) { return m.alsoCovered.indexOf(row.id) >= 0; });
      if (row.status === 'missed' && also.length) {
        extra.push(h('p', { text: 'One of your marks reached this passage, but it overlapped another planted error more. A mark counts for one error.' }));
      }
      (row.status === 'missed' ? missed : found).appendChild(defectCard(doc, d, row.status, extra));
    });
    score.marks.forEach(function (row) {
      if (row.status !== 'false_alarm') { return; }
      falseCol.appendChild(h('div', { class: 'card false', 'data-status': 'false_alarm' },
        h('blockquote', { text: clip(slice(doc, row.start, row.end), 400) }),
        h('p', { class: 'meta', text: 'You chose: ' + TYPES[row.type] + '.' }),
        h('p', { text: 'Not a planted error. The answer key covers planted errors only, so this is not a finding that the clause is sound.' })));
    });
    if (!c.found) { found.appendChild(h('p', { class: 'empty', text: 'None.' })); }
    if (!c.missed) { missed.appendChild(h('p', { class: 'empty', text: 'None.' })); }
    if (!c.falseAlarms) { falseCol.appendChild(h('p', { class: 'empty', text: 'None.' })); }

    var planted = [];
    score.defects.forEach(function (row) {
      defectsById[row.id].spans.forEach(function (sp) {
        planted.push({ id: row.id, start: sp[0], end: sp[1], status: row.status === 'missed' ? 'missed' : 'found' });
      });
    });
    var annotated = h('article', { class: 'doc reveal', 'aria-label': 'The draft with answers marked' });
    var holder = h('details', { id: 'annotated' },
      h('summary', { text: 'Show the draft with the answers marked' }),
      h('p', { class: 'small muted', text: 'Planted errors are shaded and labelled. Your own marks have a double underline.' }),
      annotated);
    holder.addEventListener('toggle', function () {
      if (holder.open && !annotated.firstChild) { renderDocument(annotated, scope, { marks: cur.marks, planted: planted }); }
    });

    var facts = [];
    if (result.timeUp) { facts.push('Time is up.'); }
    if (ex.mode === 'spot') {
      facts.push('You had ' + mmss(result.secondsAllowed) + ' for about ' + scope.words.toLocaleString('en-US') + ' words and used ' + mmss(result.secondsUsed) + '.');
    } else {
      facts.push('You spent ' + mmss(result.secondsUsed) + ' on about ' + scope.words.toLocaleString('en-US') + ' words.');
    }

    show('', [h('div', { class: 'wide' },
      h('h1', { text: 'What was planted' }),
      h('p', { class: 'muted', text: MODES[ex.mode] + ': ' + doc.title }),
      h('p', { id: 'reveal-facts', text: facts.join(' ') }),
      h('ul', { class: 'scoreline', 'aria-label': 'Score' },
        scoreItem(c.planted, 'planted errors', 'planted'),
        scoreItem(c.found, 'found', 'hits'),
        scoreItem(c.misclassified, 'of those, wrong type', 'misclassified'),
        scoreItem(c.missed, 'missed', 'missed'),
        scoreItem(c.falseAlarms, 'false alarms', 'falseAlarms'),
        c.duplicates ? scoreItem(c.duplicates, 'repeat marks', 'duplicates') : null),
      h('div', { class: 'cols' }, found, missed, falseCol),
      scope.unscored.length ? h('section', null,
        h('h2', { text: 'Also planted, not scored' }),
        h('p', { class: 'small muted', text: 'This error is a missing clause with no passage to mark, so it is left out of the score.' }),
        scope.unscored.map(function (d) { return defectCard(doc, d, 'unscored'); })) : null,
      holder,
      nextActions()
    )]);
  }

  // ------------------------------------------------------------ verify list

  function viewVerify() {
    var ex = session.exercises[session.idx];
    var doc = DOCS[ex.doc];
    var started = Date.now();
    var chosen = {};
    cur = { ex: ex, marks: [] };
    var clock = h('span', { id: 'clock', role: 'timer', text: '0:00' });
    var list = h('ol', { class: 'claims' }, doc.verify.map(function (it) {
      return h('li', null, h('label', null,
        h('input', { type: 'checkbox', 'data-item': it.id, 'aria-label': 'Check before relying on statement',
          onchange: function (e) { chosen[it.id] = e.target.checked; } }),
        h('span', { class: 'text', text: slice(doc, it.s, it.e) })));
    }));
    show('', [h('div', { class: 'page' },
      h('h1', { text: MODES.verify }),
      h('p', { class: 'muted', text: doc.title }),
      h('p', { text: 'Tick each statement you would check against the source before relying on it.' }),
      h('p', { class: 'small muted' }, 'Time spent: ', clock, '. Suggested: 3 minutes.'),
      list,
      h('div', { class: 'actions' }, h('button', { class: 'primary', id: 'finish', onclick: function () {
        var selected = Object.keys(chosen).filter(function (k) { return chosen[k]; });
        var score = S.scoreVerify(doc.verify, selected, doc.defects);
        var result = { mode: 'verify', doc: doc.id, docSha256: doc.sha256, excerpt: null,
          secondsUsed: Math.round((Date.now() - started) / 1000), secondsAllowed: null, timeUp: false, score: score };
        session.results.push(result);
        viewVerifyReveal(result);
      } }, 'Finish and see answers'))
    )]);
    timer = setInterval(function () { clock.textContent = mmss(Math.floor((Date.now() - started) / 1000)); }, 500);
  }

  function viewVerifyReveal(result) {
    var doc = DOCS[result.doc], c = result.score.counts;
    var byDefect = {};
    doc.defects.forEach(function (d) { byDefect[d.id] = d; });
    var rows = {};
    result.score.items.forEach(function (r) { rows[r.id] = r; });
    var list = h('ol', { class: 'claims' }, doc.verify.map(function (it) {
      var r = rows[it.id], d = it.defect ? byDefect[it.defect] : null;
      var line = d
        ? (r.ticked ? 'Planted error. You ticked it.' : 'Planted error. You did not tick it.')
        : (r.ticked ? 'Not planted. You ticked it: an extra check.' : 'Not planted. You did not tick it.');
      return h('li', { class: 'res', 'data-status': r.status },
        h('div', { class: 'text', text: slice(doc, it.s, it.e) }),
        h('p', null, h('span', { class: 'tag ' + (d ? (r.ticked ? 'found' : 'missed') : 'yours'), text: d ? (r.ticked ? 'Found' : 'Missed') : 'Not planted' }), line),
        d ? [h('p', null, h('strong', { text: d.title + '. ' }), d.why),
             h('p', { class: 'meta small muted', text: d.authority }),
             h('details', null, h('summary', { text: 'The rule, as read for the catalog' }),
               h('p', { class: 'small', text: DATA.catalog[d.code].rule }))] : null);
    }));
    show('', [h('div', { class: 'page' },
      h('h1', { text: 'Which ones were planted' }),
      h('p', { class: 'muted', text: MODES.verify + ': ' + doc.title }),
      h('ul', { class: 'scoreline', 'aria-label': 'Score' },
        scoreItem(c.items, 'statements', 'items'),
        scoreItem(c.planted, 'planted errors', 'planted'),
        scoreItem(c.found, 'of those, ticked', 'hits'),
        scoreItem(c.missed, 'left unticked', 'missed'),
        scoreItem(c.extraChecks, 'extra checks', 'extraChecks')),
      h('div', { class: 'note' },
        h('p', { text: 'All ' + c.items + ' statements came from the same draft and read the same way. ' + c.planted + ' of them were planted errors. The wording does not tell you which.' }),
        h('p', { text: '“Not planted” means only that the answer key does not list the statement. It is not a finding that the statement is right.' })),
      list,
      nextActions()
    )]);
  }

  // ------------------------------------------------------------ summary and result file

  function buildResult() {
    var exercises = session.results.map(function (r) {
      var doc = DOCS[r.doc];
      var out = { mode: r.mode, doc: r.doc, docSha256: r.docSha256, excerpt: r.excerpt,
        secondsUsed: r.secondsUsed, secondsAllowed: r.secondsAllowed, timeUp: r.timeUp,
        counts: r.score.counts, recall: r.score.recall, byType: r.score.byType, byCode: r.score.byCode,
        defects: r.score.defects.map(function (d) { return { id: d.id, status: d.status }; }) };
      if (r.mode === 'verify') {
        out.items = r.score.items;
      } else {
        out.marks = r.score.marks.map(function (m) {
          return { start: m.start, end: m.end, type: m.type, status: m.status, defectId: m.defectId, block: blockIndexAt(doc, m.start) };
        });
      }
      return out;
    });
    var totals = S.combine(session.results.map(function (r) { return { mode: r.mode, score: r.score }; }));
    var result = {
      schema: S.RESULT_SCHEMA, id: session.id, build: DATA.build, created: new Date().toISOString(),
      set: { id: session.set.id, area: session.set.area, length: session.set.length, rotation: session.set.rotation },
      exercises: exercises, totals: totals
    };
    store.set(result);
    return result;
  }

  function tallyTable(caption, rows, firstHead) {
    return h('div', { class: 'tablebox' }, h('table', { class: 'data' },
      h('caption', { text: caption }),
      h('thead', null, h('tr', null, h('th', { scope: 'col', text: firstHead }),
        ['Planted', 'Found', 'Wrong type', 'Missed'].map(function (t) { return h('th', { scope: 'col', class: 'num', text: t }); }))),
      h('tbody', null, rows.map(function (r) {
        return h('tr', null, h('th', { scope: 'row', text: r.label }),
          [r.t.planted, r.t.found, r.t.misclassified, r.t.missed].map(function (n) { return h('td', { class: 'num', text: String(n) }); }));
      }))));
  }

  function viewSummary(result, reopened) {
    var t = result.totals;
    var authorityOf = {};
    DATA.docs.forEach(function (d) { d.defects.forEach(function (x) { if (!authorityOf[x.code]) { authorityOf[x.code] = x.authority; } }); });
    var stale = result.build !== DATA.build;

    var exRows = result.exercises.map(function (ex) {
      var c = ex.counts, doc = DOCS[ex.doc];
      return h('tr', null,
        h('th', { scope: 'row', text: MODES[ex.mode] + (ex.excerpt ? ' (excerpt)' : '') }),
        h('td', { text: doc ? doc.title : ex.doc }),
        h('td', { class: 'num', text: String(c.planted) }),
        h('td', { class: 'num', text: String(c.found) }),
        h('td', { class: 'num', text: String(c.missed) }),
        h('td', { class: 'num', text: ex.mode === 'verify' ? plural(c.extraChecks, 'extra check', 'extra checks') : String(c.falseAlarms) }));
    });

    function save() {
      var name = 'drill-result-' + (result.set && result.set.id ? result.set.id : 'session') + '-' + result.id.slice(0, 6) + '.json';
      var blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
      var url = URL.createObjectURL(blob);
      var a = h('a', { href: url, download: name });
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      say('Result file saved as ' + name);
    }

    show('', [h('div', { class: 'wide' },
      h('h1', { text: 'Session summary' }),
      h('p', { class: 'muted', text: (result.set && result.set.length
        ? result.set.area + ', ' + result.set.length + ' minutes, rotation ' + result.set.rotation
        : 'Single exercise') + '. ' + new Date(result.created).toLocaleString() }),
      stale ? h('div', { class: 'note' }, h('p', { text: 'This summary was made with a different build of the exercise data, so document titles may not match.' })) : null,
      h('ul', { class: 'scoreline', 'aria-label': 'Totals' },
        scoreItem(t.planted, 'planted errors', 'planted'),
        scoreItem(t.found, 'found', 'hits'),
        scoreItem(t.misclassified, 'of those, wrong type', 'misclassified'),
        scoreItem(t.missed, 'missed', 'missed'),
        scoreItem(t.falseAlarms, 'false alarms', 'falseAlarms'),
        scoreItem(t.extraChecks, 'extra checks', 'extraChecks')),
      h('div', { class: 'tablebox' }, h('table', { class: 'data' },
        h('caption', { text: 'By exercise' }),
        h('thead', null, h('tr', null, ['Exercise', 'Document'].map(function (x) { return h('th', { scope: 'col', text: x }); }),
          ['Planted', 'Found', 'Missed', 'False alarms'].map(function (x) { return h('th', { scope: 'col', class: 'num', text: x }); }))),
        h('tbody', null, exRows))),
      tallyTable('By defect type', DATA.types.filter(function (x) { return t.byType[x.id]; }).map(function (x) {
        return { label: x.label, t: t.byType[x.id] };
      }), 'Type'),
      tallyTable('By rule', Object.keys(t.byCode).sort(function (a, b) {
        return a[0] === b[0] ? parseInt(a.slice(1), 10) - parseInt(b.slice(1), 10) : (a < b ? -1 : 1);
      }).map(function (code) {
        return { label: code + (authorityOf[code] ? ': ' + authorityOf[code] : ''), t: t.byCode[code] };
      }), 'Catalog rule'),
      h('p', { class: 'small muted', text: 'These numbers describe one sitting with planted errors in fictional documents. They are not a measure of legal skill. The result file holds your marks and counts and no name.' }),
      h('div', { class: 'actions' },
        h('button', { class: 'primary', id: 'save-json', onclick: save }, 'Save results as JSON'),
        h('button', { id: 'print', onclick: function () { window.print(); } }, 'Print'),
        h('button', { id: 'home', onclick: viewHome }, reopened ? 'Back to setup' : 'Start another session'))
    )]);
  }

  viewHome();
})();
