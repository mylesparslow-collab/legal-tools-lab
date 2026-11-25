// Renders an audit result as Markdown. No imports, no I/O.

const esc = (s) => String(s).replaceAll('|', '\\|').replaceAll('\n', ' ');

const OUTCOME_TEXT = {
  'gaps-found': 'One or more checks failed.',
  'needs-review': 'No check failed, but some items need attorney review.',
  'no-gaps-found': 'These checks found no gaps. That is not a finding of legal compliance.',
};

export function toMarkdown(result, scan) {
  const L = [];
  L.push(`# Progressive design-build audit: ${result.project || 'untitled project'}`);
  L.push('');
  L.push(`Agency: ${result.agency || 'not recorded'}  `);
  L.push(`As of: ${result.as_of}  `);
  L.push(`Statute text verified: ${result.rules_verified_on}  `);
  L.push(`Result: ${OUTCOME_TEXT[result.outcome]}`);
  L.push('');
  L.push(`| Pass | Fail | Review | Info | N/A |`);
  L.push(`|---|---|---|---|---|`);
  L.push(`| ${result.counts.PASS} | ${result.counts.FAIL} | ${result.counts.REVIEW} | ${result.counts.INFO} | ${result.counts['N/A']} |`);
  L.push('');
  const sections = [...new Set(result.findings.map((f) => f.section))];
  for (const s of sections) {
    L.push(`## ${s}`);
    L.push('');
    L.push('| ID | Check | Status | Citation | Detail |');
    L.push('|---|---|---|---|---|');
    for (const f of result.findings.filter((x) => x.section === s)) {
      L.push(`| ${f.id} | ${esc(f.title)} | ${f.status} | ${esc(f.citation)}${f.verification === 'primary-text' ? '' : ' (not verified)'} | ${esc(f.detail)} |`);
    }
    L.push('');
  }
  if (scan) {
    L.push('## Keyword screen of the RFQ draft');
    L.push('');
    L.push('A hit shows where related wording appears. It does not show the clause is adequate. A miss means the wording was not found, not that the element is absent.');
    L.push('');
    L.push('| Element | Citation | Found | Line | Excerpt |');
    L.push('|---|---|---|---|---|');
    for (const r of scan) L.push(`| ${esc(r.label)} | ${r.citation} | ${r.found ? 'yes' : 'no'} | ${r.line ?? ''} | ${r.excerpt ? esc(r.excerpt) : ''} |`);
    L.push('');
  }
  L.push('---');
  L.push('Portfolio demo built on fictional data. Not legal advice and not reviewed by an attorney. Statute text can change; re-verify before relying on any item.');
  L.push('');
  return L.join('\n');
}
