/*
 * Scoring for the catch-the-error drill. Pure functions, no DOM, no storage.
 * Loads in a browser (window.DrillScoring) and in Node (require).
 *
 * The matching rule
 * -----------------
 * Offsets are character positions in a document's display text. A span is
 * [start, end). A planted defect has one or more spans. A mark is one span
 * plus the defect type the trainee chose.
 *
 *  1. A mark shorter than rule.minMarkChars or longer than rule.maxMarkChars
 *     is not scored at all ("too_short", "too_long").
 *  2. A mark reaches a defect when, for at least one of the defect's spans,
 *     the overlap in characters is at least
 *         min(rule.overlapCap, max(1, floor(spanLength / 2))).
 *     With the shipped values that is 30 characters, or half the span if the
 *     span is shorter than 60 characters.
 *  3. A mark counts for one defect only: the one it overlaps most. On a tie,
 *     the defect listed first in the answer key. Other defects the mark also
 *     reaches are reported as "alsoCovered" and stay missed unless another
 *     mark finds them.
 *  4. A defect is found when at least one mark counts for it. The first such
 *     mark, in the order the marks were made, decides the type. If that
 *     mark's type is the defect's type the defect is "found"; if not it is
 *     "misclassified" (found, wrong type). Both count toward recall.
 *  5. Later marks on a defect already found are "duplicate". They are not
 *     hits and not false alarms.
 *  6. A scored mark that counts for no defect is a "false_alarm".
 *
 * Rules 2 and 3 are the eval kit's rule for a verbatim quote
 * (governance-eval-kit/eval_harness/harness/score.py, _match). Rules 4 to 6
 * add the type check, which the kit does not have. The kit's two other ways
 * of matching (a reviewer's adjudication, and a citation for a missing
 * clause) are not used here.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(); }
  else { root.DrillScoring = factory(); }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var DEFAULT_RULE = { minMarkChars: 20, maxMarkChars: 600, overlapCap: 30 };
  var RESULT_SCHEMA = 'catch-the-error-drill/result/1';

  function overlap(a, b) {
    return Math.max(0, Math.min(a[1], b[1]) - Math.max(a[0], b[0]));
  }

  function needFor(span, rule) {
    var cap = (rule || DEFAULT_RULE).overlapCap;
    return Math.min(cap, Math.max(1, Math.floor((span[1] - span[0]) / 2)));
  }

  /* Which defect does one span count for? Returns {defectId, overlap, alsoCovered}. */
  function matchSpan(span, defects, rule) {
    var best = null;
    var reached = [];
    for (var i = 0; i < defects.length; i++) {
      var d = defects[i];
      var top = 0;
      for (var j = 0; j < d.spans.length; j++) {
        var ov = overlap(span, d.spans[j]);
        if (ov >= needFor(d.spans[j], rule) && ov > top) { top = ov; }
      }
      if (top > 0) {
        reached.push(d.id);
        if (best === null || top > best.overlap) { best = { defectId: d.id, overlap: top }; }
      }
    }
    if (best === null) { return { defectId: null, overlap: 0, alsoCovered: [] }; }
    best.alsoCovered = reached.filter(function (id) { return id !== best.defectId; });
    return best;
  }

  function emptyTally() { return { planted: 0, found: 0, misclassified: 0, missed: 0 }; }

  function tallyInto(table, key, status) {
    if (!table[key]) { table[key] = emptyTally(); }
    var t = table[key];
    t.planted += 1;
    if (status === 'missed') { t.missed += 1; } else { t.found += 1; }
    if (status === 'misclassified') { t.misclassified += 1; }
  }

  /*
   * Score the marks made on one document or excerpt.
   *   defects: [{id, type, code, severity, spans: [[s, e], ...]}]  (the planted defects in view)
   *   marks:   [{id, start, end, type}] in the order they were made
   */
  function scoreMarks(defects, marks, rule) {
    rule = rule || DEFAULT_RULE;
    var byId = {};
    var defectRows = defects.map(function (d) {
      var row = { id: d.id, type: d.type, code: d.code, severity: d.severity,
                  status: 'missed', markIds: [], chosenType: null };
      byId[d.id] = row;
      return row;
    });
    var counts = { planted: defects.length, found: 0, correctType: 0, misclassified: 0, missed: 0,
                   marks: marks.length, hits: 0, falseAlarms: 0, duplicates: 0, notScored: 0 };
    var markRows = marks.map(function (m) {
      var len = m.end - m.start;
      var row = { id: m.id, start: m.start, end: m.end, type: m.type,
                  status: null, defectId: null, alsoCovered: [] };
      if (!(len >= rule.minMarkChars)) { row.status = 'too_short'; counts.notScored += 1; return row; }
      if (len > rule.maxMarkChars) { row.status = 'too_long'; counts.notScored += 1; return row; }
      var m1 = matchSpan([m.start, m.end], defects, rule);
      row.alsoCovered = m1.alsoCovered;
      if (m1.defectId === null) { row.status = 'false_alarm'; counts.falseAlarms += 1; return row; }
      row.defectId = m1.defectId;
      var d = byId[m1.defectId];
      d.markIds.push(m.id);
      if (d.status !== 'missed') { row.status = 'duplicate'; counts.duplicates += 1; return row; }
      d.chosenType = m.type;
      d.status = m.type === d.type ? 'found' : 'misclassified';
      row.status = d.status === 'found' ? 'hit' : 'misclassified';
      counts.hits += 1;
      return row;
    });
    var byType = {}, byCode = {};
    defectRows.forEach(function (d) {
      if (d.status === 'missed') { counts.missed += 1; } else { counts.found += 1; }
      if (d.status === 'found') { counts.correctType += 1; }
      if (d.status === 'misclassified') { counts.misclassified += 1; }
      tallyInto(byType, d.type, d.status);
      tallyInto(byCode, d.code, d.status);
    });
    return {
      defects: defectRows, marks: markRows, counts: counts,
      recall: counts.planted ? counts.found / counts.planted : null,
      byType: byType, byCode: byCode
    };
  }

  /*
   * Score a "Which would you verify?" list.
   *   items: [{id, defect: defectId or null}], selected: [itemId, ...]
   * A planted statement that was ticked is found. A planted statement left
   * unticked is missed. A tick on an unplanted statement is an extra check,
   * not an error: checking costs time, relying on a wrong statement costs more.
   */
  function scoreVerify(items, selected, defects) {
    var chosen = {};
    (selected || []).forEach(function (id) { chosen[id] = true; });
    var info = {};
    (defects || []).forEach(function (d) { info[d.id] = d; });
    var counts = { planted: 0, found: 0, missed: 0, extraChecks: 0, items: items.length, ticked: 0 };
    var byType = {}, byCode = {};
    var defectRows = [];
    var itemRows = items.map(function (it) {
      var ticked = !!chosen[it.id];
      if (ticked) { counts.ticked += 1; }
      var status;
      if (it.defect) {
        counts.planted += 1;
        status = ticked ? 'found' : 'missed';
        if (ticked) { counts.found += 1; } else { counts.missed += 1; }
        var d = info[it.defect] || {};
        defectRows.push({ id: it.defect, type: d.type, code: d.code, severity: d.severity, status: status });
        if (d.type) { tallyInto(byType, d.type, status); }
        if (d.code) { tallyInto(byCode, d.code, status); }
      } else {
        status = ticked ? 'extra_check' : 'left';
        if (ticked) { counts.extraChecks += 1; }
      }
      return { id: it.id, defectId: it.defect || null, ticked: ticked, status: status };
    });
    return {
      items: itemRows, defects: defectRows, counts: counts,
      recall: counts.planted ? counts.found / counts.planted : null,
      byType: byType, byCode: byCode
    };
  }

  function addTallies(into, from) {
    Object.keys(from || {}).forEach(function (k) {
      if (!into[k]) { into[k] = emptyTally(); }
      ['planted', 'found', 'misclassified', 'missed'].forEach(function (f) { into[k][f] += from[k][f]; });
    });
  }

  /* Add up the exercises of one session. exercises: [{mode, score}] */
  function combine(exercises) {
    var out = { planted: 0, found: 0, misclassified: 0, missed: 0, falseAlarms: 0, duplicates: 0,
                extraChecks: 0, recall: null, byType: {}, byCode: {}, byMode: {} };
    exercises.forEach(function (ex) {
      var c = ex.score.counts;
      out.planted += c.planted; out.found += c.found; out.missed += c.missed;
      out.misclassified += c.misclassified || 0;
      out.falseAlarms += c.falseAlarms || 0;
      out.duplicates += c.duplicates || 0;
      out.extraChecks += c.extraChecks || 0;
      addTallies(out.byType, ex.score.byType);
      addTallies(out.byCode, ex.score.byCode);
      var m = {}; m[ex.mode] = { planted: c.planted, found: c.found, misclassified: c.misclassified || 0, missed: c.missed };
      addTallies(out.byMode, m);
    });
    out.recall = out.planted ? out.found / out.planted : null;
    return out;
  }

  /* Check a saved result file. Returns a list of problems (empty if usable). */
  function validateResult(obj) {
    var problems = [];
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) { return ['not a JSON object']; }
    if (obj.schema !== RESULT_SCHEMA) { problems.push('schema is not ' + RESULT_SCHEMA); }
    if (typeof obj.build !== 'string') { problems.push('missing build id'); }
    if (!Array.isArray(obj.exercises) || !obj.exercises.length) { problems.push('no exercises'); return problems; }
    obj.exercises.forEach(function (ex, i) {
      var where = 'exercise ' + (i + 1) + ': ';
      if (['review', 'spot', 'verify'].indexOf(ex.mode) < 0) { problems.push(where + 'unknown mode'); }
      if (typeof ex.doc !== 'string') { problems.push(where + 'missing document id'); }
      if (!Array.isArray(ex.defects)) { problems.push(where + 'missing defect list'); return; }
      ex.defects.forEach(function (d) {
        if (typeof d.id !== 'string' || ['found', 'misclassified', 'missed'].indexOf(d.status) < 0) {
          problems.push(where + 'bad defect entry');
        }
      });
    });
    return problems;
  }

  /*
   * Group results for the debrief. results: saved result objects.
   * Returns per-defect counts across the group and nothing per person:
   *   defects:      [{id, doc, modes, attempts, missed, misclassified, missedShare}]
   *                 most-missed first, then by id
   *   byMode:       {mode: {planted, found, misclassified, missed}} summed over the group
   *   falseAlarms:  [{doc, block, people}] paragraphs with no planted defect that
   *                 two or more people marked, most-marked first
   * A result that lists the same defect in the same exercise mode twice counts once.
   */
  function aggregate(results) {
    var defects = {}, byMode = {}, fa = {};
    results.forEach(function (res, person) {
      var seen = {}, seenFa = {};
      res.exercises.forEach(function (ex) {
        ex.defects.forEach(function (d) {
          var k = ex.mode + '|' + d.id;
          if (seen[k]) { return; }
          seen[k] = true;
          if (!defects[d.id]) {
            defects[d.id] = { id: d.id, doc: ex.doc, modes: [], attempts: 0, missed: 0, misclassified: 0 };
          }
          var row = defects[d.id];
          if (row.modes.indexOf(ex.mode) < 0) { row.modes.push(ex.mode); }
          row.attempts += 1;
          if (d.status === 'missed') { row.missed += 1; }
          if (d.status === 'misclassified') { row.misclassified += 1; }
          tallyInto(byMode, ex.mode, d.status);
        });
        (ex.marks || []).forEach(function (m) {
          if (m.status !== 'false_alarm' || typeof m.block !== 'number') { return; }
          var k = ex.doc + '|' + m.block;
          if (seenFa[k]) { return; }
          seenFa[k] = true;
          if (!fa[k]) { fa[k] = { doc: ex.doc, block: m.block, people: 0 }; }
          fa[k].people += 1;
        });
      });
      void person;
    });
    var list = Object.keys(defects).map(function (id) {
      var r = defects[id];
      r.modes.sort();
      r.missedShare = r.attempts ? r.missed / r.attempts : 0;
      return r;
    });
    list.sort(function (a, b) {
      return (b.missedShare - a.missedShare) || (b.missed - a.missed) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
    });
    var faList = Object.keys(fa).map(function (k) { return fa[k]; })
      .filter(function (r) { return r.people >= 2; });
    faList.sort(function (a, b) {
      return (b.people - a.people) || (a.doc < b.doc ? -1 : a.doc > b.doc ? 1 : a.block - b.block);
    });
    return { people: results.length, defects: list, byMode: byMode, falseAlarms: faList };
  }

  return {
    DEFAULT_RULE: DEFAULT_RULE, RESULT_SCHEMA: RESULT_SCHEMA,
    overlap: overlap, needFor: needFor, matchSpan: matchSpan,
    scoreMarks: scoreMarks, scoreVerify: scoreVerify, combine: combine,
    validateResult: validateResult, aggregate: aggregate
  };
});
