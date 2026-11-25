// Builds demo/index.html (one self-contained page) and CORRECTIONS.md from the
// same sources the CLI uses, so the demo cannot drift from the engine.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => readFileSync(resolve(root, p), 'utf8');
const strip = (src) => src.replace(/^export\s+/gm, '');
const json = (p) => JSON.stringify(JSON.parse(read(p))).replaceAll('</', '<\\/');

const corrections = JSON.parse(read('data/corrections.json'));
const md = ['# Corrections to the research report (Tool 5)', '',
  'Checked on 2026-11-25 against leginfo.legislature.ca.gov: the chaptered text of SB 706 (Stats. 2023, ch. 500) and the current code display for Pub. Cont. Code ch. 4.7, ch. 4.1, ch. 2.9, and § 7201.', '',
  ...corrections.flatMap((c, i) => [`## ${i + 1}. ${c.topic}`, '', `- Report says: ${c.report}`, `- Primary text: ${c.primary}`, `- Effect: ${c.effect}`, '']),
  'Not legal advice. Prepared by a non-attorney for a portfolio demo.', ''].join('\n');
writeFileSync(resolve(root, 'CORRECTIONS.md'), md);

const html = read('demo/template.html')
  .replace('/*__ENGINE__*/', () => strip(read('src/engine.js')))
  .replace('"__RULES__"', () => json('data/rules.json'))
  .replace('"__CORRECTIONS__"', () => json('data/corrections.json'))
  .replace('"__SAMPLE_GOOD__"', () => json('samples/compliant.json'))
  .replace('"__SAMPLE_BAD__"', () => json('samples/flawed.json'));
writeFileSync(resolve(root, 'demo/index.html'), html);
console.log('Wrote demo/index.html and CORRECTIONS.md');
