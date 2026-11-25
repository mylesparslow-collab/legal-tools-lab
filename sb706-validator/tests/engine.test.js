import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validate, checkAuthority, checkProposer, checkSubcontracts, checkWorkforceMonths, checkGmpAndRetention, checkLegislatureReport, checkAwardAndBonds, checkRfq, subcontractThreshold, requiredGraduatePct } from '../src/engine.js';
import { scanRfqText } from '../src/rfq_scan.js';
import { toMarkdown } from '../src/report.js';

const load = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), 'utf8'));
const rules = load('../data/rules.json');
const good = () => load('../samples/compliant.json');
const bad = () => load('../samples/flawed.json');
const AS_OF = '2026-11-25';
const byId = (fs, id) => fs.find((f) => f.id === id);
const auth = (rec, asOf = AS_OF) => checkAuthority(rec, rules, asOf);

test('rules data: every rule has a citation and a known verification status', () => {
  for (const [k, r] of Object.entries(rules.rules)) {
    assert.ok(r.citation, `${k} citation`);
    assert.ok(['primary-text', 'not-verified'].includes(r.status), `${k} status`);
    if (r.status === 'primary-text') assert.ok(rules.meta.sources[r.source], `${k} source url`);
  }
});

test('rules data: cites chapter 4.7 (22185 series), not the water-agency chapter 4.1', () => {
  const text = JSON.stringify(rules.rules);
  assert.ok(text.includes('22185.1'));
  assert.ok(!/§§? ?2217[0-4]/.test(text), 'no rule should cite §§ 22170-22174');
  assert.equal(rules.rules.max_projects_per_agency.value, 10);
  assert.equal(rules.rules.min_project_value_exclusive.value, 5000000);
  assert.equal(rules.rules.chapter_repeal_date.value, '2030-01-01');
  assert.equal(rules.rules.legislature_report_due.value, '2028-12-31');
  assert.equal(rules.rules.subcontract_rule_min_contract_value.value, 10000000);
});

test('compliant sample: no failures and no review items', () => {
  const r = validate(good(), rules);
  assert.equal(r.counts.FAIL, 0);
  assert.equal(r.counts.REVIEW, 0);
  assert.equal(r.outcome, 'no-gaps-found');
});

test('flawed sample: expected failures are raised', () => {
  const r = validate(bad(), rules);
  assert.equal(r.outcome, 'gaps-found');
  const failed = r.findings.filter((f) => f.status === 'FAIL').map((f) => f.id);
  for (const id of ['AUTH-3', 'AUTH-4', 'AUTH-6', 'RFQ-2', 'RFQ-6', 'RFQ-8', 'TPL-E', 'TPL-G', 'RFQ-W1', 'RFQ-N', 'SOQ1-SAFE', 'SOQ1-CERT', 'SOQ1-STW', 'SOQ2-STW', 'AWD-2', 'BND-1', 'BND-3', 'BND-4', 'GMP-2', 'GMP-3', 'RET-1', 'RET-2', 'RET-S1', 'SUB-1', 'STW-1', 'STW-2', 'LEG-3']) {
    assert.ok(failed.includes(id), `${id} should fail`);
  }
});

test('project value: exactly $5,000,000 fails, one dollar more passes', () => {
  const r = good();
  r.project.estimated_cost = 5000000;
  assert.equal(byId(auth(r), 'AUTH-3').status, 'FAIL');
  r.project.estimated_cost = 5000001;
  assert.equal(byId(auth(r), 'AUTH-3').status, 'PASS');
});

test('project cap: tenth project passes, eleventh fails', () => {
  const r = good();
  r.agency.prior_ch47_projects = 9;
  assert.equal(byId(auth(r), 'AUTH-4').status, 'PASS');
  r.agency.prior_ch47_projects = 10;
  assert.equal(byId(auth(r), 'AUTH-4').status, 'FAIL');
});

test('agency type: special district goes to review, state agency fails', () => {
  const r = good();
  r.agency.type = 'special_district';
  assert.equal(byId(auth(r), 'AUTH-1').status, 'REVIEW');
  r.agency.type = 'state_agency';
  assert.equal(byId(auth(r), 'AUTH-1').status, 'FAIL');
});

test('state facility is excluded', () => {
  const r = good();
  r.project.state_owned_or_operated_facility = true;
  assert.equal(byId(auth(r), 'AUTH-2').status, 'FAIL');
});

test('sunset: award on the repeal date fails, the day before passes, late phase 2 is review', () => {
  const r = good();
  r.dates = { rfq_issue: '2029-06-01', contract_award: '2030-01-01' };
  assert.equal(byId(auth(r), 'AUTH-5').status, 'FAIL');
  r.dates.contract_award = '2029-12-31';
  assert.equal(byId(auth(r), 'AUTH-5').status, 'PASS');
  r.dates.phase2_amendment = '2030-02-01';
  assert.equal(byId(auth(r), 'AUTH-5').status, 'REVIEW');
  assert.equal(byId(auth(r, '2030-01-01'), 'AUTH-5').status, 'FAIL');
});

test('safety record: EMR average of exactly 1.00 passes, above fails, ADR alternative is review', () => {
  const p = good().proposers[0];
  p.safety.emr_last_3_years = [1.1, 0.9, 1.0];
  assert.equal(byId(checkProposer(p, rules, 0), 'SOQ1-SAFE').status, 'PASS');
  p.safety.emr_last_3_years = [1.1, 0.9, 1.01];
  assert.equal(byId(checkProposer(p, rules, 0), 'SOQ1-SAFE').status, 'FAIL');
  p.safety.adr_party_labor_code_3201_5 = true;
  assert.equal(byId(checkProposer(p, rules, 0), 'SOQ1-SAFE').status, 'REVIEW');
});

test('safety record: recordable rate above the standard fails even with a good EMR', () => {
  const p = good().proposers[0];
  p.safety.trir_avg = 3.0;
  assert.equal(byId(checkProposer(p, rules, 0), 'SOQ1-SAFE').status, 'FAIL');
});

test('workforce: PLA renewal needs an original agreement before 2023-01-01', () => {
  const p = good().proposers[0];
  p.workforce = { pla_exception: 'agency_pla_renewal', original_pla_date: '2022-12-31' };
  assert.equal(byId(checkProposer(p, rules, 0), 'SOQ1-STW').status, 'PASS');
  p.workforce.original_pla_date = '2023-01-01';
  assert.equal(byId(checkProposer(p, rules, 0), 'SOQ1-STW').status, 'FAIL');
  p.workforce = {};
  assert.equal(byId(checkProposer(p, rules, 0), 'SOQ1-STW').status, 'FAIL');
});

test('perjury certification: joint venture members must certify too', () => {
  const p = good().proposers[1];
  p.certification.by_all_general_partners_or_jv_members = false;
  assert.equal(byId(checkProposer(p, rules, 1), 'SOQ2-CERT').status, 'FAIL');
});

test('conflict of interest: a team member who worked on the solicitation is sent to review', () => {
  const p = good().proposers[0];
  p.team_members = [{ name: 'Advisor X', performed_solicitation_services_for_agency: true }];
  const f = byId(checkProposer(p, rules, 0), 'SOQ1-COI');
  assert.equal(f.status, 'REVIEW');
  assert.equal(f.verification, 'not-verified');
});

test('subcontract threshold: 0.5% of construction price, only at $10M or more', () => {
  assert.equal(subcontractThreshold({ total_value: 12400000, construction_allocable_price: 10800000 }, rules).threshold, 54000);
  assert.equal(subcontractThreshold({ total_value: 9999999.99, construction_allocable_price: 9000000 }, rules).applies, false);
  assert.equal(subcontractThreshold({ total_value: 10000000, construction_allocable_price: 9000000 }, rules).applies, true);
});

test('subcontracts: at the threshold is exempt, one dollar over needs the process, SOQ-listed is excepted', () => {
  const r = bad();
  const fs = checkSubcontracts(r, rules);
  assert.equal(byId(fs, 'SUB-2').status, 'N/A');
  assert.equal(byId(fs, 'SUB-3').status, 'PASS');
  assert.equal(byId(fs, 'SUB-1').status, 'FAIL');
  r.subcontracts[0].listed_in_soq = true;
  assert.equal(byId(checkSubcontracts(r, rules), 'SUB-1').status, 'N/A');
});

test('subcontracts: rule does not apply under $10M; missing construction price is review', () => {
  const r = bad();
  r.contract.total_value = 9000000;
  assert.equal(checkSubcontracts(r, rules)[0].status, 'N/A');
  r.contract.total_value = 12000000;
  delete r.contract.construction_allocable_price;
  assert.equal(checkSubcontracts(r, rules)[0].status, 'REVIEW');
});

test('graduate percentage: 60 by default, 30 for listed trades, none for teamster', () => {
  assert.equal(requiredGraduatePct('electrician', rules), 60);
  assert.equal(requiredGraduatePct('Carpenter', rules), 30);
  assert.equal(requiredGraduatePct('operating engineer', rules), 30);
  assert.equal(requiredGraduatePct('teamster', rules), null);
});

test('workforce month: passes on either headcount or hours', () => {
  const row = { contractor: 'A', occupation: 'electrician', month: '2028-01', report_submitted: true, journeypersons: 10, graduate_journeypersons: 5, journeyperson_hours: 1000, graduate_hours: 600 };
  assert.equal(checkWorkforceMonths({ workforce_months: [row] }, rules)[0].status, 'PASS');
  row.graduate_hours = 599;
  assert.equal(checkWorkforceMonths({ workforce_months: [row] }, rules)[0].status, 'FAIL');
  row.graduate_journeypersons = 6;
  assert.equal(checkWorkforceMonths({ workforce_months: [row] }, rules)[0].status, 'PASS');
});

test('workforce month: under 10 hours and small unlisted subs are not applicable', () => {
  const tiny = { contractor: 'A', occupation: 'electrician', month: '2028-01', report_submitted: true, journeypersons: 1, graduate_journeypersons: 0, journeyperson_hours: 9, graduate_hours: 0 };
  assert.equal(checkWorkforceMonths({ workforce_months: [tiny] }, rules)[0].status, 'N/A');
  const sub = { contractor: 'S', occupation: 'electrician', month: '2028-01', report_submitted: true, is_subcontractor: true, listed_subcontractor: false, subcontract_value: 50000, journeypersons: 4, graduate_journeypersons: 0, journeyperson_hours: 400, graduate_hours: 0 };
  assert.equal(checkWorkforceMonths({ contract: { total_value: 10000000 }, workforce_months: [sub] }, rules)[0].status, 'N/A');
  sub.subcontract_value = 50001;
  assert.equal(checkWorkforceMonths({ contract: { total_value: 10000000 }, workforce_months: [sub] }, rules)[0].status, 'FAIL');
});

test('workforce month: failing month states 150% withholding', () => {
  const f = checkWorkforceMonths(bad(), rules)[0];
  assert.equal(f.status, 'FAIL');
  assert.match(f.detail, /\$330,000/);
});

test('retention: 5% passes, above fails, phase 1 must be zero', () => {
  const r = good();
  assert.equal(byId(checkGmpAndRetention(r, rules), 'RET-2').status, 'PASS');
  r.retention.prime_rate = 0.0501;
  assert.equal(byId(checkGmpAndRetention(r, rules), 'RET-2').status, 'FAIL');
  r.retention.phase1_rate = 0.01;
  assert.equal(byId(checkGmpAndRetention(r, rules), 'RET-1').status, 'FAIL');
  r.retention.bonds_required_in_solicitation = false;
  assert.equal(byId(checkGmpAndRetention(r, rules), 'RET-2').status, 'REVIEW');
});

test('retention: higher subcontract rate allowed only with bond notice and no bond', () => {
  const r = good();
  r.retention.subcontract_rates = [{ name: 'X', rate: 0.1 }];
  assert.equal(byId(checkGmpAndRetention(r, rules), 'RET-S1').status, 'FAIL');
  r.retention.subcontract_rates = [{ name: 'X', rate: 0.1, bond_notice_given: true, sub_failed_to_furnish_bond: true }];
  assert.equal(byId(checkGmpAndRetention(r, rules), 'RET-S1').status, 'PASS');
});

test('GMP: savings split follows the written agreement; overrun is the entity’s', () => {
  const g = byId(checkGmpAndRetention(good(), rules), 'GMP-1');
  assert.match(g.detail, /\$800,000 under/);
  assert.match(g.detail, /25% = \$200,000/);
  const o = byId(checkGmpAndRetention(bad(), rules), 'GMP-1');
  assert.match(o.detail, /by \$750,000/);
});

test('GMP off-ramp: other entities need a written determination and a best value award', () => {
  const r = good();
  r.gmp = { agreed: false, offramp: { solicited_from: 'other_entities', written_best_interest_determination: false, award_basis: 'low_bid' } };
  const fs = checkGmpAndRetention(r, rules);
  assert.equal(byId(fs, 'GMP-4').status, 'FAIL');
  assert.equal(byId(fs, 'GMP-5').status, 'FAIL');
  r.gmp.offramp = { solicited_from: 'soq_firms' };
  assert.equal(byId(checkGmpAndRetention(r, rules), 'GMP-4').status, 'PASS');
});

test('bonds: payment bond must be at least the performance bond', () => {
  const r = good();
  r.bonds.payment_bond_amount = r.bonds.performance_bond_amount - 1;
  assert.equal(byId(checkAwardAndBonds(r, rules), 'BND-1').status, 'FAIL');
});

test('RFQ: price as the only weighted factor fails qualifications-based selection', () => {
  const r = good();
  r.rfq.factors = [{ name: 'Price', weight: 100, price_related: true }];
  assert.equal(byId(checkRfq(r, rules), 'RFQ-W3').status, 'FAIL');
});

test('RFQ: weights that do not total 100 produce a note, not a failure', () => {
  const r = good();
  r.rfq.factors[0].weight = 30;
  assert.equal(byId(checkRfq(r, rules), 'RFQ-W2').status, 'INFO');
});

test('Legislature report: due 2028-12-31', () => {
  const r = good();
  assert.equal(byId(checkLegislatureReport(r, rules, '2028-12-31'), 'LEG-1').status, 'INFO');
  assert.equal(byId(checkLegislatureReport(r, rules, '2029-01-01'), 'LEG-1').status, 'FAIL');
  r.legislature_report = { submitted: true, submitted_on: '2028-12-31' };
  assert.equal(byId(checkLegislatureReport(r, rules, '2029-01-01'), 'LEG-1').status, 'PASS');
  r.legislature_report.submitted_on = '2029-01-02';
  assert.equal(byId(checkLegislatureReport(r, rules, '2029-02-01'), 'LEG-1').status, 'FAIL');
});

test('validate requires an as-of date', () => {
  const r = good();
  delete r.as_of;
  assert.throws(() => validate(r, rules));
  assert.equal(validate(r, rules, { asOf: AS_OF }).as_of, AS_OF);
});

test('RFQ keyword screen: finds present wording with a line number, reports misses', () => {
  const scan = scanRfqText(readFileSync(new URL('../samples/flawed_rfq.txt', import.meta.url), 'utf8'));
  const k = (key) => scan.find((s) => s.key === key);
  assert.equal(k('project_description').found, true);
  assert.equal(k('project_description').line, 5);
  assert.equal(k('perjury_certification').found, false);
  assert.equal(k('expected_cost_range').found, false);
  assert.equal(k('tpl_safety_record').found, false);
});

test('Markdown report: includes every finding id and the disclaimer', () => {
  const r = validate(bad(), rules);
  const md = toMarkdown(r, null);
  for (const f of r.findings) assert.ok(md.includes(`| ${f.id} |`));
  assert.match(md, /Not legal advice/);
});
