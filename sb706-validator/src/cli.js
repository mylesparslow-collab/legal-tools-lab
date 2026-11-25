#!/usr/bin/env node
// Usage: node src/cli.js <record.json> [--rfq draft.txt] [--as-of YYYY-MM-DD] [--out path/prefix]
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { validate } from './engine.js';
import { scanRfqText } from './rfq_scan.js';
import { toMarkdown } from './report.js';

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (name) => { const i = args.indexOf(name); return i >= 0 ? args.splice(i, 2)[1] : undefined; };
const rfqPath = flag('--rfq');
const asOf = flag('--as-of');
const out = flag('--out');
const recordPath = args[0];

if (!recordPath) {
  console.error('Usage: node src/cli.js <record.json> [--rfq draft.txt] [--as-of YYYY-MM-DD] [--out path/prefix]');
  process.exit(2);
}

const rules = JSON.parse(readFileSync(resolve(here, '../data/rules.json'), 'utf8'));
const record = JSON.parse(readFileSync(recordPath, 'utf8'));
const result = validate(record, rules, { asOf });
const scan = rfqPath ? scanRfqText(readFileSync(rfqPath, 'utf8')) : null;
const md = toMarkdown(result, scan);

if (out) {
  mkdirSync(dirname(resolve(out)), { recursive: true });
  writeFileSync(out + '.json', JSON.stringify({ ...result, rfq_scan: scan }, null, 2) + '\n');
  writeFileSync(out + '.md', md);
  console.log(`Wrote ${out}.json and ${out}.md  (pass ${result.counts.PASS}, fail ${result.counts.FAIL}, review ${result.counts.REVIEW})`);
} else {
  process.stdout.write(md);
}
process.exit(result.counts.FAIL ? 1 : 0);
