/* Catch-the-error drill: facilitator page. Adds up saved result files on this device. */
(function () {
  'use strict';

  var DATA = window.DRILL_DATA;
  var S = window.DrillScoring;
  var main = document.getElementById('main');
  var live = document.getElementById('live');

  var MODES = { review: 'Review an AI draft', spot: 'Timed spot check', verify: 'Which would you verify?' };
  var DOCS = {}, DEFECTS = {};
  DATA.docs.forEach(function (d) {
    DOCS[d.id] = d;
    d.defects.forEach(function (x) { DEFECTS[x.id] = { doc: d, defect: x }; });
  });

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
  function docText(doc) {
    if (!doc._text) { doc._text = doc.blocks.map(function (b) { return b.x; }).join('\n'); }
    return doc._text;
  }
  function clip(str, n) { return str.length > n ? str.slice(0, n - 1).trimEnd() + '…' : str; }
  function pct(a, b) { return b ? Math.round(100 * a / b) + '%' : 'n/a'; }

  var loaded = [];    // accepted result objects
  var skipped = [];   // {name, reason}
  var out = h('div', { id: 'group' });
  var statusEl = h('p', { id: 'load-status', role: 'status', text: 'No result files loaded.' });

  // Check one parsed file against this build of the exercise. Returns a reason to skip it, or null.
  function reject(obj) {
    var problems = S.validateResult(obj);
    if (problems.length) { return 'not a result file (' + problems[0] + ')'; }
    if (obj.build !== DATA.build) { return 'made with a different build of the exercise data'; }
    if (loaded.some(function (r) { return r.id === obj.id; })) { return 'already loaded'; }
    for (var i = 0; i < obj.exercises.length; i++) {
      var ex = obj.exercises[i];
      if (!DOCS[ex.doc]) { return 'refers to an unknown document'; }
      if (ex.defects.some(function (d) { return !DEFECTS[d.id]; })) { return 'refers to an unknown planted error'; }
    }
    return null;
  }

  function addFiles(files) {
    var pending = files.length;
    if (!pending) { return; }
    Array.prototype.forEach.call(files, function (file) {
      var reader = new FileReader();
      reader.onload = function () {
        var obj = null, reason = null;
        try { obj = JSON.parse(String(reader.result)); } catch (e) { reason = 'not valid JSON'; }
        if (!reason) { reason = reject(obj); }
        if (reason) { skipped.push({ name: file.name, reason: reason }); } else { loaded.push(obj); }
        if (--pending === 0) { draw(); }
      };
      reader.onerror = function () {
        skipped.push({ name: file.name, reason: 'could not be read' });
        if (--pending === 0) { draw(); }
      };
      reader.readAsText(file);
    });
  }

  function draw() {
    out.textContent = '';
    statusEl.textContent = loaded.length
      ? loaded.length + (loaded.length === 1 ? ' result file loaded.' : ' result files loaded.')
      : 'No result files loaded.';
    if (skipped.length) {
      out.appendChild(h('div', { class: 'note', id: 'skipped' },
        h('p', { text: skipped.length + (skipped.length === 1 ? ' file was skipped:' : ' files were skipped:') }),
        h('ul', null, skipped.map(function (s) { return h('li', { text: s.name + ': ' + s.reason }); }))));
    }
    live.textContent = statusEl.textContent;
    if (!loaded.length) { return; }
    var agg = S.aggregate(loaded);

    out.appendChild(h('h2', { text: 'By exercise' }));
    out.appendChild(h('p', { class: 'small muted', text: 'Each planted error counts once for each person who had it in front of them.' }));
    out.appendChild(h('div', { class: 'tablebox' }, h('table', { class: 'data', id: 'by-mode' },
      h('thead', null, h('tr', null, h('th', { scope: 'col', text: 'Exercise' }),
        ['Planted errors seen', 'Found', 'Missed', 'Share found'].map(function (t) { return h('th', { scope: 'col', class: 'num', text: t }); }))),
      h('tbody', null, ['spot', 'verify', 'review'].filter(function (m) { return agg.byMode[m]; }).map(function (m) {
        var t = agg.byMode[m];
        return h('tr', { 'data-mode': m }, h('th', { scope: 'row', text: MODES[m] }),
          h('td', { class: 'num', text: String(t.planted) }), h('td', { class: 'num', text: String(t.found) }),
          h('td', { class: 'num', text: String(t.missed) }), h('td', { class: 'num', text: pct(t.found, t.planted) }));
      })))));

    out.appendChild(h('h2', { text: 'Debrief list: planted errors, most-missed first' }));
    var rows = agg.defects.filter(function (r) { return r.missed > 0; });
    if (!rows.length) { out.appendChild(h('p', { class: 'empty', text: 'Nobody missed anything that was in front of them.' })); }
    out.appendChild(h('div', { id: 'debrief' }, rows.map(function (r) {
      var info = DEFECTS[r.id], d = info.defect, doc = info.doc;
      return h('div', { class: 'card missed', 'data-defect': r.id },
        h('h3', { text: 'Missed by ' + r.missed + ' of ' + r.attempts + ': ' + d.title }),
        h('p', { class: 'meta', text: doc.title + '. ' + r.modes.map(function (m) { return MODES[m]; }).join(', ') + '.' +
          (r.misclassified ? ' ' + r.misclassified + ' found it and chose the wrong type.' : '') }),
        d.spans.map(function (sp) { return h('blockquote', { text: docText(doc).slice(sp[0], sp[1]) }); }),
        h('p', { text: d.why }),
        h('p', { class: 'meta', text: d.authority }),
        h('details', null, h('summary', { text: 'The rule, as read for the catalog' }),
          h('p', { text: DATA.catalog[d.code].rule })));
    })));
    var caught = agg.defects.length - rows.length;
    if (caught) { out.appendChild(h('p', { class: 'small muted', text: caught + ' other planted ' + (caught === 1 ? 'error was' : 'errors were') + ' found by everyone who saw ' + (caught === 1 ? 'it.' : 'them.') })); }

    out.appendChild(h('h2', { text: 'Marked by two or more people, not planted' }));
    out.appendChild(h('p', { class: 'small muted', text: 'The answer key covers planted errors only. A passage listed here may be worth a look in the debrief; the key does not say it is sound.' }));
    if (!agg.falseAlarms.length) { out.appendChild(h('p', { class: 'empty', text: 'None.' })); }
    out.appendChild(h('div', { id: 'shared-false-alarms' }, agg.falseAlarms.map(function (r) {
      var doc = DOCS[r.doc], b = doc.blocks[r.block];
      return h('div', { class: 'card false' },
        h('h3', { text: 'Marked by ' + r.people + ' people' }),
        h('p', { class: 'meta', text: doc.title }),
        h('blockquote', { text: b ? clip(b.x, 500) : '' }));
    })));
    out.appendChild(h('div', { class: 'actions' }, h('button', { onclick: function () { window.print(); } }, 'Print')));
  }

  var input = h('input', { type: 'file', id: 'files', multiple: true, accept: '.json,application/json',
    onchange: function (e) { addFiles(e.target.files); e.target.value = ''; } });

  main.textContent = '';
  main.appendChild(h('div', { class: 'wide' },
    h('h1', { text: 'Group results' }),
    h('p', { class: 'lede', text: 'Load the result files the group saved at the end of the session. This page adds them up on this device and shows which planted errors most people missed.' }),
    h('div', { class: 'note' },
      h('p', { text: 'Results are shown for the group only. The files carry no names, and this page has no per-person table or ranking.' }),
      h('p', { text: 'Personal portfolio demo. Fictional documents. Not legal advice and not reviewed by an attorney.' })),
    h('p', null, h('label', { for: 'files', text: 'Result files (JSON) ' }), input),
    h('div', { class: 'actions' }, h('button', { id: 'clear', onclick: function () { loaded = []; skipped = []; draw(); } }, 'Clear')),
    statusEl,
    out,
    h('p', { class: 'small muted', text: 'Exercise data build ' + DATA.build + '. Session plan and debrief points are in FACILITATOR_GUIDE.md.' })
  ));
})();
