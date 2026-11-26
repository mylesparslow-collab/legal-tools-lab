/*
 * Browser smoke test. Opens the app from file:// in Chromium and drives it.
 * Run: node tests/smoke.js
 * Writes screenshots to docs/. Exits 1 on the first failed check.
 */
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const INDEX = 'file://' + path.join(ROOT, 'index.html');
const FACILITATOR = 'file://' + path.join(ROOT, 'facilitator.html');
const DOCS_DIR = path.join(ROOT, 'docs');
const DATA = require(path.join(ROOT, 'app', 'data.js'));

let passed = 0;
function ok(name) { passed += 1; console.log('ok   ' + name); }

function watch(page, problems) {
  page.on('pageerror', (e) => problems.push('page error: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') { problems.push('console error: ' + m.text()); } });
  page.on('request', (r) => { if (!r.url().startsWith('file://') && !r.url().startsWith('blob:')) { problems.push('network request: ' + r.url()); } });
}

// Select [start, end) of the document's display text, the way a mouse drag would.
async function selectSpan(page, docId, start, end) {
  await page.evaluate(([docId, start, end]) => {
    const doc = window.DRILL_DATA.docs.find((d) => d.id === docId);
    const bi = doc.blocks.findIndex((b) => b.s <= start && start < b.s + b.x.length);
    const b = doc.blocks[bi];
    const el = document.querySelector('#doc .blk[data-b="' + bi + '"]');
    function locate(offset) {
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let node, seen = 0;
      while ((node = walker.nextNode())) {
        if (offset <= seen + node.length) { return [node, offset - seen]; }
        seen += node.length;
      }
      throw new Error('offset outside block');
    }
    const range = document.createRange();
    const a = locate(start - b.s), z = locate(end - b.s);
    range.setStart(a[0], a[1]);
    range.setEnd(z[0], z[1]);
    el.scrollIntoView({ block: 'center' });
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }, [docId, start, end]);
  await page.waitForFunction(() => !document.querySelector('.types button').disabled);
}

async function count(page, key) {
  return parseInt(await page.locator('[data-count="' + key + '"]').first().textContent(), 10);
}

// A paragraph with no planted error in it, inside the given section range.
function cleanParagraph(doc, from, to) {
  const spans = doc.defects.flatMap((d) => d.spans);
  return doc.blocks.find((b) => b.t === 'p' && b.sec >= from && b.sec <= to && b.x.length >= 80 && b.x.length <= 500 &&
    !spans.some(([s, e]) => s < b.s + b.x.length && b.s < e));
}

async function startSingle(page, mode, docId, query) {
  await page.goto(INDEX + (query || ''));
  await page.locator('#single > summary').click();
  await page.selectOption('#single-mode', mode);
  await page.selectOption('#single-doc', docId);
  await page.click('#start-single');
  await page.click('#begin');
}

(async () => {
  fs.mkdirSync(DOCS_DIR, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'drill-smoke-'));
  const browser = await chromium.launch();
  const problems = [];
  const saved = [];

  try {
    // 1. One drill from a session set: one planted span, one wrong span.
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2, acceptDownloads: true });
    const page = await ctx.newPage();
    watch(page, problems);
    await page.goto(INDEX);
    assert.ok(page.url().startsWith('file://'));
    await page.getByLabel('Commercial lease').check();
    await page.getByLabel('20 minutes').check();
    const set = DATA.sets.find((s) => s.area === 'Commercial lease' && s.length === 20 && s.rotation === 'A');
    assert.strictEqual(await page.locator('#plan li').count(), set.exercises.length);
    await page.click('#start-session');
    ok('home page opens from file:// and shows the session plan');

    // Exercise 1: timed spot check. Mark nothing, finish early.
    await page.click('#begin');
    await page.waitForSelector('#doc .blk');
    assert.match(await page.locator('#clock').textContent(), /^[45]:\d\d$/);
    await page.click('#finish');
    assert.strictEqual(await count(page, 'hits'), 0);
    const spotDoc = DATA.docs.find((d) => d.id === set.exercises[0].doc);
    assert.strictEqual(await count(page, 'missed'), spotDoc.defects.length);
    ok('timed spot check with no marks reveals every planted error as missed');
    await page.click('#next');

    // Exercise 2: verify list. Tick one planted and one unplanted statement.
    await page.click('#begin');
    const vdoc = DATA.docs.find((d) => d.id === set.exercises[1].doc);
    const plantedItem = vdoc.verify.find((i) => i.defect), otherItem = vdoc.verify.find((i) => !i.defect);
    await page.locator('[data-item="' + plantedItem.id + '"]').check();
    await page.locator('[data-item="' + otherItem.id + '"]').check();
    await page.click('#finish');
    assert.strictEqual(await count(page, 'hits'), 1);
    assert.strictEqual(await count(page, 'extraChecks'), 1);
    assert.strictEqual(await count(page, 'missed'), vdoc.verify.filter((i) => i.defect).length - 1);
    ok('verify list scores one planted statement ticked and one extra check');
    await page.click('#next');

    // Exercise 3: review an excerpt. This is the drill the quality bar names.
    await page.click('#begin');
    const ex = set.exercises[2];
    const doc = DATA.docs.find((d) => d.id === ex.doc);
    const excerpt = doc.excerpts[ex.excerpt];
    const defect = doc.defects.find((d) => d.id === excerpt.defects[0]);
    const [ds, de] = defect.spans[0];
    await selectSpan(page, doc.id, ds, de);
    await page.click('.types button[data-type="' + defect.type + '"]');
    assert.strictEqual(await page.locator('#marks li button.remove').count(), 1);
    assert.strictEqual(await page.locator('#doc mark.um').first().textContent(), defect.spans[0] && await page.evaluate(
      ([id, s, e]) => window.DRILL_DATA.docs.find((d) => d.id === id).blocks.map((b) => b.x).join('\n').slice(s, e), [doc.id, ds, de]));
    const wrong = cleanParagraph(doc, excerpt.from, excerpt.to);
    await selectSpan(page, doc.id, wrong.s, wrong.s + 60);
    await page.screenshot({ path: path.join(DOCS_DIR, 'drill.png') });
    await page.click('.types button[data-type="clause_high"]');
    assert.strictEqual(await page.locator('#marks li button.remove').count(), 2);
    await page.click('#finish');
    await page.waitForSelector('.cols');
    assert.strictEqual(await count(page, 'hits'), 1, 'exactly one hit');
    assert.strictEqual(await count(page, 'falseAlarms'), 1, 'exactly one false alarm');
    assert.strictEqual(await count(page, 'misclassified'), 0);
    assert.strictEqual(await count(page, 'missed'), excerpt.defects.length - 1);
    assert.strictEqual(await page.locator('.col-found .card').count(), 1);
    assert.strictEqual(await page.locator('.col-false .card').count(), 1);
    assert.strictEqual(await page.locator('.col-missed .card').count(), excerpt.defects.length - 1);
    assert.ok((await page.locator('.col-found .card').textContent()).includes(defect.why), 'the catalog explanation is shown');
    await page.screenshot({ path: path.join(DOCS_DIR, 'reveal.png') });
    ok('review drill: one planted span and one wrong span score exactly one hit and one false alarm');

    // The annotated draft labels the planted spans.
    await page.locator('#annotated > summary').click();
    await page.waitForSelector('#annotated mark.pl.found');
    assert.strictEqual(await page.locator('#annotated .tag.missed').count(), excerpt.defects.length - 1);
    ok('annotated draft shows found and missed spans');

    // Summary and the saved result file.
    await page.click('#next');
    assert.strictEqual(await count(page, 'hits'), 2);
    assert.strictEqual(await count(page, 'falseAlarms'), 1);
    const [download] = await Promise.all([page.waitForEvent('download'), page.click('#save-json')]);
    const file1 = path.join(tmp, 'a.json');
    await download.saveAs(file1);
    const result = JSON.parse(fs.readFileSync(file1, 'utf8'));
    assert.strictEqual(result.schema, 'catch-the-error-drill/result/1');
    assert.strictEqual(result.build, DATA.build);
    assert.strictEqual(result.exercises.length, 3);
    assert.strictEqual(result.totals.found, 2);
    assert.ok(!JSON.stringify(result).match(/"name"/), 'no name field in the result');
    saved.push(file1);
    await page.screenshot({ path: path.join(DOCS_DIR, 'summary.png'), fullPage: true });
    ok('summary totals are right and the result saves as JSON');

    // The last summary can be reopened from storage.
    await page.click('#home');
    await page.click('#reopen');
    assert.strictEqual(await count(page, 'hits'), 2);
    ok('last summary reopens from localStorage');
    await ctx.close();

    // 2. Keyboard only: mark a sentence without a pointer, wrong type on the right place.
    const kctx = await browser.newContext({ viewport: { width: 1280, height: 860 } });
    const kpage = await kctx.newPage();
    watch(kpage, problems);
    const kdoc = DATA.docs.find((d) => d.id === 'emp-01');
    await startSingle(kpage, 'review', 'emp-01');
    const kdef = kdoc.defects.find((d) => d.type === 'clause_high');
    const kblock = kdoc.blocks.findIndex((b) => b.s <= kdef.spans[0][0] && kdef.spans[0][0] < b.s + b.x.length);
    const textBlocks = kdoc.blocks.map((b, i) => (b.x.length ? i : -1)).filter((i) => i >= 0);
    await kpage.locator('#doc .blk[tabindex="0"]').focus();
    await kpage.keyboard.press('Tab');
    await kpage.keyboard.press('Shift+Tab');
    for (let i = 0; i < textBlocks.indexOf(kblock); i++) { await kpage.keyboard.press('ArrowDown'); }
    assert.strictEqual(await kpage.evaluate(() => document.activeElement.getAttribute('data-b')), String(kblock));
    // Step through sentences until the target overlaps the planted span, then press 3 (the wrong type).
    let reached = false;
    for (let i = 0; i < 40 && !reached; i++) {
      await kpage.keyboard.press('ArrowRight');
      reached = await kpage.evaluate(([s, e]) => {
        const kt = document.querySelector('#doc .kt');
        if (!kt) { return false; }
        const blk = kt.closest('.blk');
        const b = window.DRILL_DATA.docs.find((d) => d.id === 'emp-01').blocks[+blk.getAttribute('data-b')];
        const r = document.createRange(); r.selectNodeContents(blk); r.setEnd(kt.firstChild, 0);
        const a = b.s + r.toString().length;
        const all = blk.querySelectorAll('.kt'); let len = 0; all.forEach((n) => { len += n.textContent.length; });
        return Math.min(e, a + len) - Math.max(s, a) >= 30;
      }, kdef.spans[0]);
    }
    assert.ok(reached, 'arrow keys reach the sentence holding the planted span');
    await kpage.keyboard.press('3');
    assert.strictEqual(await kpage.locator('#marks li button.remove').count(), 1);
    assert.match(await kpage.locator('#mark-status').textContent(), /Marked/);
    // Remove and re-add with the keyboard to check the list is operable.
    await kpage.locator('#marks li button.remove').focus();
    await kpage.keyboard.press('Enter');
    assert.strictEqual(await kpage.locator('#marks li button.remove').count(), 0);
    await kpage.locator('#doc .blk[tabindex="0"]').focus();
    await kpage.keyboard.press('3');
    await kpage.locator('#finish').focus();
    await kpage.keyboard.press('Enter');
    assert.strictEqual(await count(kpage, 'hits'), 1);
    assert.strictEqual(await count(kpage, 'misclassified'), 1);
    assert.strictEqual(await count(kpage, 'falseAlarms'), 0);
    assert.strictEqual(await kpage.locator('.card[data-status="misclassified"]').count(), 1);
    ok('keyboard-only marking works and a wrong type on the right place is found, misclassified');
    await kctx.close();

    // 3. Storage blocked, timed run that expires, on a tablet-sized dark screen.
    const bctx = await browser.newContext({ viewport: { width: 820, height: 1180 }, deviceScaleFactor: 2, colorScheme: 'dark', acceptDownloads: true });
    await bctx.addInitScript(() => {
      Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('blocked', 'SecurityError'); } });
    });
    const bpage = await bctx.newPage();
    watch(bpage, problems);
    await startSingle(bpage, 'spot', 'pw-02', '?seconds=4');
    const pdoc = DATA.docs.find((d) => d.id === 'pw-02');
    const pdef = pdoc.defects[0];
    await selectSpan(bpage, 'pw-02', pdef.spans[0][0] + 5, pdef.spans[0][1] - 5);
    await bpage.click('.types button[data-type="' + pdef.type + '"]');
    await bpage.screenshot({ path: path.join(DOCS_DIR, 'drill-tablet-dark.png') });
    await bpage.waitForSelector('.cols', { timeout: 10000 });
    assert.match(await bpage.locator('#reveal-facts').textContent(), /Time is up/);
    assert.strictEqual(await count(bpage, 'hits'), 1);
    assert.strictEqual(await count(bpage, 'missed'), pdoc.defects.length - 1);
    await bpage.screenshot({ path: path.join(DOCS_DIR, 'reveal-tablet-dark.png') });
    await bpage.click('#next');
    assert.strictEqual(await count(bpage, 'hits'), 1);
    const [d2] = await Promise.all([bpage.waitForEvent('download'), bpage.click('#save-json')]);
    const file2 = path.join(tmp, 'b.json');
    await d2.saveAs(file2);
    saved.push(file2);
    await bpage.click('#home');
    assert.strictEqual(await bpage.locator('#reopen').count(), 0);
    assert.strictEqual(await bpage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, 'no sideways scroll on a tablet');
    ok('with storage blocked the timed run expires, reveals, summarises and saves');
    await bctx.close();

    // 4. A too-long selection is refused with a message.
    const lctx = await browser.newContext({ viewport: { width: 1280, height: 860 } });
    const lpage = await lctx.newPage();
    watch(lpage, problems);
    await startSingle(lpage, 'review', 'lease-01');
    const ldoc = DATA.docs.find((d) => d.id === 'lease-01');
    const long = ldoc.blocks.find((b) => b.t === 'p' && b.x.length > DATA.rule.maxMarkChars + 50);
    await selectSpan(lpage, 'lease-01', long.s, long.s + long.x.length);
    await lpage.click('.types button[data-type="clause_high"]');
    assert.match(await lpage.locator('#mark-status').textContent(), /Too long/);
    assert.strictEqual(await lpage.locator('#marks li button.remove').count(), 0);
    // lease-01 has one planted error with no passage to mark: shown, not scored.
    await lpage.click('#finish');
    assert.strictEqual(await count(lpage, 'planted'), ldoc.defects.length);
    assert.ok((await lpage.locator('main').textContent()).includes(ldoc.unscored[0].title));
    ok('over-long marks are refused, and the unanchored missing clause is shown but not scored');
    await lctx.close();

    // 5. Facilitator page: load two saved files plus one bad file.
    const fctx = await browser.newContext({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2 });
    const fpage = await fctx.newPage();
    watch(fpage, problems);
    await fpage.goto(FACILITATOR);
    const bad = path.join(tmp, 'bad.json');
    fs.writeFileSync(bad, '{"hello": 1}');
    // A second person's file for the same session: same marks, new id.
    const second = JSON.parse(fs.readFileSync(saved[0], 'utf8'));
    second.id = 'second-person';
    const file3 = path.join(tmp, 'c.json');
    fs.writeFileSync(file3, JSON.stringify(second));
    await fpage.setInputFiles('#files', [saved[0], saved[1], file3, bad]);
    await fpage.waitForSelector('#debrief .card');
    assert.match(await fpage.locator('#load-status').textContent(), /^3 result files loaded/);
    assert.match(await fpage.locator('#skipped').textContent(), /bad\.json/);
    assert.match(await fpage.locator('#debrief .card h3').first().textContent(), /^Missed by 2 of 2/);
    assert.strictEqual(await fpage.locator('#by-mode tbody tr').count(), 3);
    assert.strictEqual(await fpage.locator('#shared-false-alarms .card').count(), 1);
    assert.strictEqual(await fpage.locator('main').getByText(/rank|leaderboard/i).count(), 1, 'ranking is mentioned only in the notice that there is none');
    await fpage.screenshot({ path: path.join(DOCS_DIR, 'facilitator.png') });
    ok('facilitator page adds up result files, lists most-missed errors and skips a bad file');
    await fctx.close();

    assert.deepStrictEqual(problems, [], 'no page errors, console errors or network requests');
    ok('no page errors, console errors or network requests in any run');
    console.log('\n' + passed + ' checks passed');
  } finally {
    await browser.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})().catch((err) => { console.error('\nFAILED: ' + (err && err.stack ? err.stack : err)); process.exit(1); });
