// SB 706 progressive design-build validator: deterministic checks.
// Pure functions, no imports, no I/O. Every legal number comes from the rules
// object (data/rules.json), never from a literal in this file.
//
// Statuses:
//   PASS   - the record satisfies the check as the engine reads the statute
//   FAIL   - the record does not satisfy it
//   REVIEW - the statute is silent or ambiguous, or a needed input is missing
//   INFO   - a computed number or reminder, not a pass/fail judgment
//   N/A    - the check does not apply to this record

export const STATUS = Object.freeze({ PASS: 'PASS', FAIL: 'FAIL', REVIEW: 'REVIEW', INFO: 'INFO', NA: 'N/A' });

const money = (n) => '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 });
const pct = (f) => (Math.round(f * 10000) / 100) + '%';
const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const isDate = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v);
const avg = (a) => a.reduce((s, x) => s + x, 0) / a.length;
const daysBetween = (a, b) => Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / 86400000);

function rule(rules, key) {
  const r = rules.rules[key];
  if (!r) throw new Error(`Unknown rule key: ${key}`);
  return r;
}

function mk(rules, id, section, title, status, ruleKeys, detail, citationOverride) {
  const keys = [].concat(ruleKeys || []);
  const rs = keys.map((k) => rule(rules, k));
  return {
    id, section, title, status,
    citation: citationOverride || [...new Set(rs.map((r) => r.citation))].join('; '),
    verification: rs.some((r) => r.status !== 'primary-text') ? 'not-verified' : 'primary-text',
    rule_keys: keys,
    detail,
  };
}

// ---------------------------------------------------------------- authority

export function checkAuthority(rec, rules, asOf) {
  const out = [];
  const S = 'Authority';
  const a = rec.agency || {};
  const p = rec.project || {};

  const types = rule(rules, 'eligible_agency_types').value;
  if (!a.type) {
    out.push(mk(rules, 'AUTH-1', S, 'Agency is a local agency', STATUS.REVIEW, 'eligible_agency_types', 'Agency type is missing from the record.'));
  } else if (!types.includes(a.type)) {
    out.push(mk(rules, 'AUTH-1', S, 'Agency is a local agency', a.type === 'other' ? STATUS.REVIEW : STATUS.FAIL, 'eligible_agency_types',
      `Agency type “${a.type}” is not a city, county, city and county, or special district.` + (a.type === 'other' ? ' Recorded as “other”; needs a legal determination.' : '')));
  } else if (a.type === 'special_district') {
    out.push(mk(rules, 'AUTH-1', S, 'Agency is a local agency', STATUS.REVIEW, 'eligible_agency_types',
      `Recorded as a special district${a.type_detail ? ` (${a.type_detail})` : ''}. The chapter does not define “special district”, so confirm this entity qualifies.`));
  } else {
    out.push(mk(rules, 'AUTH-1', S, 'Agency is a local agency', STATUS.PASS, 'eligible_agency_types', `Agency type is ${a.type.replaceAll('_', ' ')}.`));
  }

  if (typeof p.state_owned_or_operated_facility !== 'boolean') {
    out.push(mk(rules, 'AUTH-2', S, 'Not a state-owned or state-operated facility', STATUS.REVIEW, 'state_facility_exclusion', 'The record does not say whether the facility is state-owned or state-operated.'));
  } else {
    out.push(mk(rules, 'AUTH-2', S, 'Not a state-owned or state-operated facility', p.state_owned_or_operated_facility ? STATUS.FAIL : STATUS.PASS, 'state_facility_exclusion',
      p.state_owned_or_operated_facility ? 'The project is on a state-owned or state-operated facility, which the chapter excludes.' : 'The project is not on a state-owned or state-operated facility.'));
  }

  const min = rule(rules, 'min_project_value_exclusive').value;
  if (!isNum(p.estimated_cost)) {
    out.push(mk(rules, 'AUTH-3', S, `Project value exceeds ${money(min)}`, STATUS.REVIEW, 'min_project_value_exclusive', 'No estimated project cost in the record.'));
  } else {
    const ok = p.estimated_cost > min;
    out.push(mk(rules, 'AUTH-3', S, `Project value exceeds ${money(min)}`, ok ? STATUS.PASS : STATUS.FAIL, 'min_project_value_exclusive',
      `Estimated cost is ${money(p.estimated_cost)}; the statute requires more than ${money(min)}` + (p.estimated_cost === min ? ' (exactly the threshold is not “in excess of” it).' : '.')));
  }

  const cap = rule(rules, 'max_projects_per_agency').value;
  if (!Number.isInteger(a.prior_ch47_projects) || a.prior_ch47_projects < 0) {
    out.push(mk(rules, 'AUTH-4', S, `Agency project count stays within ${cap}`, STATUS.REVIEW, 'max_projects_per_agency', 'The count of the agency’s earlier chapter 4.7 projects is missing.'));
  } else {
    const n = a.prior_ch47_projects + 1;
    out.push(mk(rules, 'AUTH-4', S, `Agency project count stays within ${cap}`, n <= cap ? STATUS.PASS : STATUS.FAIL, 'max_projects_per_agency',
      `This would be project ${n} of ${cap} (${a.prior_ch47_projects} earlier). ${n <= cap ? `${cap - n} remain after this one.` : 'The cap is exceeded.'}` +
      (a.ch41_water_projects ? ` The agency also reports ${a.ch41_water_projects} project(s) under the separate water-agency chapter 4.1 (SB 991); the engine does not count those here.` : '')));
  }

  const from = rule(rules, 'chapter_operative_from').value;
  const repeal = rule(rules, 'chapter_repeal_date').value;
  const d = rec.dates || {};
  const steps = [['RFQ issue', d.rfq_issue], ['contract award', d.contract_award]].filter(([, v]) => isDate(v));
  const late = [['phase 2 amendment', d.phase2_amendment], ['expected completion', d.expected_completion]].filter(([, v]) => isDate(v));
  const badSteps = steps.filter(([, v]) => v >= repeal || v < from);
  if (asOf >= repeal) {
    out.push(mk(rules, 'AUTH-5', S, 'Procurement falls inside the chapter’s life', STATUS.FAIL, ['chapter_operative_from', 'chapter_repeal_date'], `As of ${asOf} the chapter has been repealed (${repeal}).`));
  } else if (badSteps.length) {
    out.push(mk(rules, 'AUTH-5', S, 'Procurement falls inside the chapter’s life', STATUS.FAIL, ['chapter_operative_from', 'chapter_repeal_date'],
      badSteps.map(([k, v]) => `${k} dated ${v}`).join('; ') + ` falls outside ${from} to ${repeal}.`));
  } else if (!steps.length) {
    out.push(mk(rules, 'AUTH-5', S, 'Procurement falls inside the chapter’s life', STATUS.REVIEW, ['chapter_operative_from', 'chapter_repeal_date'], 'No RFQ or award date in the record.'));
  } else {
    const after = late.filter(([, v]) => v >= repeal);
    out.push(mk(rules, 'AUTH-5', S, 'Procurement falls inside the chapter’s life', after.length ? STATUS.REVIEW : STATUS.PASS, ['chapter_operative_from', 'chapter_repeal_date'],
      steps.map(([k, v]) => `${k} ${v}`).join(', ') + ` fall before the ${repeal} repeal (${daysBetween(asOf, repeal)} days from ${asOf}).` +
      (after.length ? ` But ${after.map(([k, v]) => `${k} (${v})`).join(' and ')} would come on or after repeal, and the chapter does not address contracts in progress at that date.` : '')));
  }

  if (typeof a.coi_guidelines_adopted !== 'boolean') {
    out.push(mk(rules, 'AUTH-6', S, 'Organizational conflict-of-interest guidelines developed', STATUS.REVIEW, 'coi_guidelines_required', 'The record does not say whether the agency has developed the guidelines.'));
  } else {
    out.push(mk(rules, 'AUTH-6', S, 'Organizational conflict-of-interest guidelines developed', a.coi_guidelines_adopted ? STATUS.PASS : STATUS.FAIL, 'coi_guidelines_required',
      a.coi_guidelines_adopted ? 'Agency reports guidelines are in place.' : 'Agency has not developed the required guidelines.'));
  }
  return out;
}

// ---------------------------------------------------------------- RFQ

export function checkRfq(rec, rules) {
  const out = [];
  const S = 'Request for qualifications';
  const rfq = rec.rfq;
  if (!rfq) return [mk(rules, 'RFQ-0', S, 'RFQ contents', STATUS.NA, 'rfq_elements', 'No RFQ in the record.')];

  const el = rfq.elements || {};
  rule(rules, 'rfq_elements').value.forEach((e, i) => {
    const v = el[e.key];
    out.push(mk(rules, `RFQ-${i + 1}`, S, e.label, v === true ? STATUS.PASS : v === false ? STATUS.FAIL : STATUS.REVIEW, 'rfq_elements',
      v === true ? 'Present.' : v === false ? 'Missing from the RFQ.' : 'Not recorded.', 'Pub. Cont. Code ' + e.citation));
  });

  const ti = rfq.template_items || {};
  rule(rules, 'template_items').value.forEach((e, i) => {
    const v = ti[e.key];
    out.push(mk(rules, `TPL-${String.fromCharCode(65 + i)}`, S, 'Template asks for: ' + e.label, v === true ? STATUS.PASS : v === false ? STATUS.FAIL : STATUS.REVIEW, 'template_items',
      v === true ? 'Present.' : v === false ? 'Missing from the template.' : 'Not recorded.', 'Pub. Cont. Code ' + e.citation));
  });

  if (Array.isArray(rfq.factors) && rfq.factors.length) {
    const unweighted = rfq.factors.filter((f) => !isNum(f.weight));
    const total = rfq.factors.reduce((s, f) => s + (isNum(f.weight) ? f.weight : 0), 0);
    const nonPrice = rfq.factors.filter((f) => !f.price_related && isNum(f.weight) && f.weight > 0);
    if (unweighted.length) {
      out.push(mk(rules, 'RFQ-W1', S, 'Every listed factor has a weight', STATUS.FAIL, 'rfq_elements', `No weight for: ${unweighted.map((f) => f.name).join(', ')}.`, 'Pub. Cont. Code § 22185.3(a)(3)'));
    } else {
      out.push(mk(rules, 'RFQ-W1', S, 'Every listed factor has a weight', STATUS.PASS, 'rfq_elements', `${rfq.factors.length} factors, each weighted.`, 'Pub. Cont. Code § 22185.3(a)(3)'));
      if (Math.abs(total - 100) > 1e-9) {
        out.push(mk(rules, 'RFQ-W2', S, 'Weights add up', STATUS.INFO, 'rfq_elements', `Weights total ${total}, not 100. The statute does not require a 100-point scale; this is an arithmetic note only.`, 'Arithmetic check (no statutory rule)'));
      }
    }
    out.push(mk(rules, 'RFQ-W3', S, 'Price is not the sole basis of award', nonPrice.length ? STATUS.PASS : STATUS.FAIL, 'qbs_definition',
      nonPrice.length ? `${nonPrice.length} weighted non-price factor(s).` : 'Every weighted factor is price-related, which is not a qualifications-based selection.', 'Pub. Cont. Code § 22185(i)'));
  }

  if (typeof rfq.stw_notice_in_bid_documents === 'boolean') {
    out.push(mk(rules, 'RFQ-N', S, 'Bid documents give notice of the skilled and trained workforce requirement', rfq.stw_notice_in_bid_documents ? STATUS.PASS : STATUS.FAIL, 'stw_notice',
      rfq.stw_notice_in_bid_documents ? 'Notice is included.' : 'Notice is missing. Under § 2600.5 the omission does not excuse the requirement.', 'Pub. Cont. Code §§ 2600(c), 2600.5'));
  }
  return out;
}

// ---------------------------------------------------------------- proposers

export function checkProposer(pr, rules, idx = 0) {
  const out = [];
  const S = `Proposer: ${pr.name || 'unnamed #' + (idx + 1)}`;
  const id = (s) => `SOQ${idx + 1}-${s}`;

  // Safety record, § 22185.3(a)(4)(G)
  const sf = pr.safety || {};
  const emrMax = rule(rules, 'safety_emr_max_avg').value;
  const haveEmr = Array.isArray(sf.emr_last_3_years) && sf.emr_last_3_years.length === 3 && sf.emr_last_3_years.every(isNum);
  const haveRates = [sf.trir_avg, sf.trir_standard, sf.lost_work_rate_avg, sf.lost_work_rate_standard].every(isNum);
  if (haveEmr && haveRates) {
    const e = avg(sf.emr_last_3_years);
    const emrOk = e <= emrMax + 1e-12;
    const ratesOk = sf.trir_avg <= sf.trir_standard && sf.lost_work_rate_avg <= sf.lost_work_rate_standard;
    const desc = `Three-year average EMR ${e.toFixed(3)} (limit ${emrMax.toFixed(2)}); recordable rate ${sf.trir_avg} vs standard ${sf.trir_standard}; lost work rate ${sf.lost_work_rate_avg} vs standard ${sf.lost_work_rate_standard}.`;
    if (emrOk && ratesOk) out.push(mk(rules, id('SAFE'), S, 'Acceptable safety record', STATUS.PASS, 'safety_emr_max_avg', desc));
    else if (sf.adr_party_labor_code_3201_5) out.push(mk(rules, id('SAFE'), S, 'Acceptable safety record', STATUS.REVIEW, 'safety_emr_max_avg', desc + ' The rate tests are not met; the proposer relies on being party to a Labor Code § 3201.5 alternative dispute resolution system. Confirm that reading of the “or” clause.'));
    else out.push(mk(rules, id('SAFE'), S, 'Acceptable safety record', STATUS.FAIL, 'safety_emr_max_avg', desc));
  } else if (sf.adr_party_labor_code_3201_5) {
    out.push(mk(rules, id('SAFE'), S, 'Acceptable safety record', STATUS.REVIEW, 'safety_emr_max_avg', 'Rate data incomplete; proposer relies on a Labor Code § 3201.5 alternative dispute resolution system. Confirm that reading of the “or” clause.'));
  } else {
    out.push(mk(rules, id('SAFE'), S, 'Acceptable safety record', STATUS.REVIEW, 'safety_emr_max_avg', 'Safety data incomplete: need three years of EMR, average recordable and lost work rates, and the standards for the business category.'));
  }

  // Perjury certification, § 22185.3(a)(5)
  const c = pr.certification || {};
  const partnersOk = !pr.has_general_partners_or_jv_members || c.by_all_general_partners_or_jv_members === true;
  const certOk = c.by_entity === true && partnersOk;
  out.push(mk(rules, id('CERT'), S, 'Information certified under penalty of perjury', certOk ? STATUS.PASS : STATUS.FAIL, 'rfq_elements',
    certOk ? 'Certified by the entity' + (pr.has_general_partners_or_jv_members ? ' and its general partners or joint venture members.' : '.') :
      (c.by_entity === true ? 'Entity certified, but not all general partners or joint venture members did.' : 'No certification by the entity.'), 'Pub. Cont. Code § 22185.3(a)(5)'));

  // Skilled and trained workforce, § 22185.3(b)
  const w = pr.workforce || {};
  const cutoff = rule(rules, 'pla_renewal_cutoff').value;
  let st, det;
  if (w.enforceable_stw_commitment === true) { st = STATUS.PASS; det = 'Enforceable skilled and trained workforce commitment provided (§ 22185.3(b)(1)).'; }
  else if (w.pla_exception === 'agency_pla') { st = w.entity_agrees_to_agency_pla === true ? STATUS.PASS : STATUS.FAIL; det = st === STATUS.PASS ? 'Agency project labor agreement binds all contractors and the entity agrees to be bound (§ 22185.3(b)(2)(A)).' : 'Agency project labor agreement claimed, but the entity has not agreed to be bound.'; }
  else if (w.pla_exception === 'agency_pla_renewal') {
    if (!isDate(w.original_pla_date)) { st = STATUS.REVIEW; det = 'Renewal exception claimed but the original agreement date is missing.'; }
    else { st = w.original_pla_date < cutoff ? STATUS.PASS : STATUS.FAIL; det = `Renewal of an agency project labor agreement first entered ${w.original_pla_date}; the exception needs a date before ${cutoff} (§ 22185.3(b)(2)(B)).`; }
  } else if (w.pla_exception === 'entity_pla') { st = STATUS.PASS; det = 'Entity’s own project labor agreement binds it and all subcontractors at every tier (§ 22185.3(b)(2)(C)).'; }
  else { st = STATUS.FAIL; det = 'No enforceable commitment and no project labor agreement exception. The entity “shall not be evaluated for selection”.'; }
  out.push(mk(rules, id('STW'), S, 'Skilled and trained workforce commitment or exception', st, ['stw_commitment', 'pla_renewal_cutoff'], det, 'Pub. Cont. Code § 22185.3(b)'));

  // Organizational conflict of interest, § 22185.2
  if (pr.performed_solicitation_services_for_agency === true || (pr.team_members || []).some((m) => m.performed_solicitation_services_for_agency)) {
    const who = [pr.performed_solicitation_services_for_agency ? pr.name : null, ...(pr.team_members || []).filter((m) => m.performed_solicitation_services_for_agency).map((m) => m.name)].filter(Boolean);
    out.push(mk(rules, id('COI'), S, 'Organizational conflict of interest', STATUS.REVIEW, ['coi_guidelines_required', 'gov_code_1090'],
      `${who.join(', ')} performed services for the agency relating to this solicitation. Apply the agency’s § 22185.2 guidelines. The research report also points to Gov. Code § 1090; that statute was not read for this build.`));
  }
  return out;
}

// ---------------------------------------------------------------- award, bonds

export function checkAwardAndBonds(rec, rules) {
  const out = [];
  const S = 'Award, bonds, and insurance';
  const aw = rec.award;
  if (aw && aw.issued) {
    out.push(mk(rules, 'AWD-1', S, 'Award publicly announced with the awardee named', aw.publicly_announced === true ? STATUS.PASS : STATUS.FAIL, 'award_announcement', aw.publicly_announced === true ? 'Announced.' : 'No public announcement recorded.', 'Pub. Cont. Code § 22185.3(d)'));
    out.push(mk(rules, 'AWD-2', S, 'Statement of the basis of the award', aw.basis_statement === true ? STATUS.PASS : STATUS.FAIL, 'award_announcement', aw.basis_statement === true ? 'Statement on file.' : 'No basis-of-award statement recorded. The statement and contract file must be enough to satisfy an external audit.', 'Pub. Cont. Code § 22185.3(d)'));
  }
  const b = rec.bonds;
  if (b) {
    if (isNum(b.payment_bond_amount) && isNum(b.performance_bond_amount)) {
      const ok = b.payment_bond_amount >= b.performance_bond_amount * rule(rules, 'payment_bond_min_ratio_to_performance').value;
      out.push(mk(rules, 'BND-1', S, 'Payment bond is at least the performance bond', ok ? STATUS.PASS : STATUS.FAIL, 'payment_bond_min_ratio_to_performance',
        `Payment bond ${money(b.payment_bond_amount)}; performance bond ${money(b.performance_bond_amount)}.` + (ok ? '' : ` Short by ${money(b.performance_bond_amount - b.payment_bond_amount)}.`)));
    } else out.push(mk(rules, 'BND-1', S, 'Payment bond is at least the performance bond', STATUS.REVIEW, 'payment_bond_min_ratio_to_performance', 'Bond amounts missing.'));
    out.push(mk(rules, 'BND-2', S, 'Bonds issued by a California admitted surety', b.surety_california_admitted === true ? STATUS.PASS : b.surety_california_admitted === false ? STATUS.FAIL : STATUS.REVIEW, 'bond_and_insurance_terms', b.surety_california_admitted === true ? 'Surety recorded as California admitted.' : b.surety_california_admitted === false ? 'Surety is not California admitted.' : 'Surety status not recorded.', 'Pub. Cont. Code § 22185.4(a)'));
    out.push(mk(rules, 'BND-3', S, 'Contract requires errors and omissions insurance for design', b.eo_insurance_required_in_contract === true ? STATUS.PASS : STATUS.FAIL, 'bond_and_insurance_terms', b.eo_insurance_required_in_contract === true ? 'Required.' : 'Not required in the contract.', 'Pub. Cont. Code § 22185.4(b)'));
    out.push(mk(rules, 'BND-4', S, 'Agency has a standard bond form for design-build projects', b.agency_standard_bond_form === true ? STATUS.PASS : STATUS.FAIL, 'bond_and_insurance_terms', b.agency_standard_bond_form === true ? 'Standard form exists.' : 'No standard form recorded.', 'Pub. Cont. Code § 22185.4(c)'));
  }
  return out;
}

// ---------------------------------------------------------------- GMP, retention

export function checkGmpAndRetention(rec, rules) {
  const out = [];
  const S = 'Guaranteed maximum price and retention';
  const g = rec.gmp;
  if (g) {
    if (g.agreed === true && isNum(g.amount)) {
      if (isNum(g.projected_cost_to_complete)) {
        const diff = g.projected_cost_to_complete - g.amount;
        if (diff > 0) {
          out.push(mk(rules, 'GMP-1', S, 'Cost against the guaranteed maximum price', STATUS.INFO, 'gmp_terms', `Projected cost ${money(g.projected_cost_to_complete)} exceeds the guaranteed maximum price ${money(g.amount)} by ${money(diff)}. That excess is the design-build entity’s responsibility.`, 'Pub. Cont. Code § 22185.5(b)(2)'));
        } else {
          const share = isNum(g.savings_share_to_entity) ? g.savings_share_to_entity : 0;
          const hasAgr = g.written_savings_agreement === true;
          out.push(mk(rules, 'GMP-1', S, 'Cost against the guaranteed maximum price', STATUS.INFO, 'gmp_terms',
            `Projected cost ${money(g.projected_cost_to_complete)} is ${money(-diff)} under the guaranteed maximum price ${money(g.amount)}. ` +
            (hasAgr ? `Under the prior written agreement the entity’s share is ${pct(share)} = ${money(-diff * share)}; the agency keeps ${money(-diff * (1 - share))}.` : 'With no prior written sharing agreement, the entity is not entitled to any of the difference.'), 'Pub. Cont. Code § 22185.5(b)(2)'));
        }
      }
      if (isNum(g.savings_share_to_entity) && g.savings_share_to_entity > 0) {
        out.push(mk(rules, 'GMP-2', S, 'Shared savings rest on a prior written agreement', g.written_savings_agreement === true ? STATUS.PASS : STATUS.FAIL, 'gmp_terms',
          g.written_savings_agreement === true ? 'Written agreement on file.' : `The contract gives the entity ${pct(g.savings_share_to_entity)} of savings without a prior written agreement.`, 'Pub. Cont. Code § 22185.5(b)(2)'));
      }
      if (typeof g.contract_shifts_overrun_to_agency === 'boolean') {
        out.push(mk(rules, 'GMP-3', S, 'Overruns above the guaranteed maximum price stay with the entity', g.contract_shifts_overrun_to_agency ? STATUS.FAIL : STATUS.PASS, 'gmp_terms',
          g.contract_shifts_overrun_to_agency ? 'A contract clause moves overruns to the agency. The statute allows an amendment for unforeseen site conditions; anything broader conflicts with it.' : 'No clause shifts overruns to the agency.', 'Pub. Cont. Code § 22185.5(b)'));
      }
    } else if (g.agreed === false || g.agency_elected_not_to_proceed === true) {
      const o = g.offramp || {};
      if (!o.solicited_from) {
        out.push(mk(rules, 'GMP-4', S, 'Path after no guaranteed maximum price agreement', STATUS.INFO, 'gmp_terms', 'No agreement on price. The agency may solicit proposals from firms that submitted statements of qualifications, or, on a written best-interest determination, from other design-build entities, with award on a best value basis.', 'Pub. Cont. Code § 22185.5(c)(1)'));
      } else {
        if (o.solicited_from === 'other_entities') {
          out.push(mk(rules, 'GMP-4', S, 'Written best-interest determination before soliciting other entities', o.written_best_interest_determination === true ? STATUS.PASS : STATUS.FAIL, 'gmp_terms', o.written_best_interest_determination === true ? 'Determination on file.' : 'Other design-build entities were solicited without the written determination.', 'Pub. Cont. Code § 22185.5(c)(1)'));
          out.push(mk(rules, 'GMP-5', S, 'Replacement award made on a best value basis', o.award_basis === 'best_value' ? STATUS.PASS : STATUS.FAIL, 'gmp_terms', `Award basis recorded as “${o.award_basis || 'not recorded'}”.`, 'Pub. Cont. Code § 22185.5(c)(1)'));
        } else {
          out.push(mk(rules, 'GMP-4', S, 'Proposals solicited from firms that submitted statements of qualifications', STATUS.PASS, 'gmp_terms', 'Solicited from the original responders.', 'Pub. Cont. Code § 22185.5(c)(1)'));
        }
        if (o.agency_using_prior_stamped_designs === true) {
          out.push(mk(rules, 'GMP-6', S, 'Use of the replaced entity’s designs', STATUS.INFO, 'gmp_terms', 'The agency is using the replaced entity’s complete and stamped designs. Its design professionals keep sole liability for their design errors and omissions.', 'Pub. Cont. Code § 22185.5(c)(2)'));
        }
      }
    }
  }

  const r = rec.retention;
  if (r) {
    const cap = rule(rules, 'retention_cap').value;
    if (isNum(r.phase1_rate)) {
      out.push(mk(rules, 'RET-1', S, 'No retention on work to establish the guaranteed maximum price', r.phase1_rate === 0 ? STATUS.PASS : STATUS.FAIL, 'retention_cap', r.phase1_rate === 0 ? 'Phase 1 retention is zero.' : `Phase 1 retention is ${pct(r.phase1_rate)}; it must be zero.`));
    }
    if (isNum(r.prime_rate)) {
      if (r.bonds_required_in_solicitation === true) {
        out.push(mk(rules, 'RET-2', S, `Retention from the design-build entity is at most ${pct(cap)}`, r.prime_rate <= cap ? STATUS.PASS : STATUS.FAIL, 'retention_cap', `Rate is ${pct(r.prime_rate)}; cap is ${pct(cap)} because bonds are required in the solicitation.`));
      } else {
        const gcap = rule(rules, 'general_retention_cap').value;
        out.push(mk(rules, 'RET-2', S, `Retention from the design-build entity is at most ${pct(gcap)}`, STATUS.REVIEW, ['retention_cap', 'general_retention_cap'],
          `Rate is ${pct(r.prime_rate)}. The chapter’s cap is conditioned on bonds being required in the solicitation, which is not recorded here. The general ${pct(gcap)} cap in § 7201 may still apply` + (r.prime_rate > gcap ? ', and this rate is above it.' : '.')));
      }
      (r.subcontract_rates || []).forEach((s, i) => {
        if (!isNum(s.rate)) return;
        const over = s.rate > r.prime_rate;
        const excused = over && s.bond_notice_given === true && s.sub_failed_to_furnish_bond === true;
        out.push(mk(rules, `RET-S${i + 1}`, S, `Subcontract retention does not exceed the prime rate: ${s.name}`, !over ? STATUS.PASS : excused ? STATUS.PASS : STATUS.FAIL, 'retention_cap',
          `Subcontract rate ${pct(s.rate)}; prime rate ${pct(r.prime_rate)}.` + (excused ? ' Higher rate allowed: written bond notice was given at or before bid request and the subcontractor did not furnish a bond.' : over ? ' No bond-notice exception recorded.' : ''), 'Pub. Cont. Code § 22185.7(b)'));
      });
    }
  }
  return out;
}

// ---------------------------------------------------------------- subcontracts

export function subcontractThreshold(contract, rules) {
  const frac = rule(rules, 'subcontract_threshold_fraction').value;
  const minVal = rule(rules, 'subcontract_rule_min_contract_value').value;
  if (!contract || !isNum(contract.total_value)) return { applies: null, threshold: null, reason: 'Contract value missing.' };
  if (contract.total_value < minVal) return { applies: false, threshold: null, reason: `Contract value ${money(contract.total_value)} is below ${money(minVal)}, so § 22185.6(b) does not apply.` };
  if (!isNum(contract.construction_allocable_price)) return { applies: true, threshold: null, reason: 'Contract price allocable to construction work is missing.' };
  return { applies: true, threshold: contract.construction_allocable_price * frac, reason: `${pct(frac)} of ${money(contract.construction_allocable_price)} allocable to construction.` };
}

export function checkSubcontracts(rec, rules) {
  const out = [];
  const S = 'Construction subcontracts';
  const subs = rec.subcontracts;
  if (!Array.isArray(subs) || !subs.length) return out;
  const t = subcontractThreshold(rec.contract, rules);
  if (t.applies === null || (t.applies && t.threshold === null)) {
    return [mk(rules, 'SUB-0', S, 'Subcontract award threshold', STATUS.REVIEW, ['subcontract_threshold_fraction', 'subcontract_rule_min_contract_value'], t.reason)];
  }
  if (t.applies === false) {
    return [mk(rules, 'SUB-0', S, 'Subcontract award threshold', STATUS.NA, ['subcontract_threshold_fraction', 'subcontract_rule_min_contract_value'], t.reason)];
  }
  out.push(mk(rules, 'SUB-0', S, 'Subcontract award threshold', STATUS.INFO, ['subcontract_threshold_fraction', 'subcontract_rule_min_contract_value'], `Threshold is ${money(t.threshold)} (${t.reason}) Subcontracts above it, other than those listed in the statement of qualifications, need the § 22185.6(b) process.`));
  subs.forEach((s, i) => {
    const title = `${s.name || 'Subcontract ' + (i + 1)} (${isNum(s.value) ? money(s.value) : 'value missing'})`;
    const id = `SUB-${i + 1}`;
    const keys = ['subcontract_threshold_fraction', 'subcontract_rule_min_contract_value'];
    if (!isNum(s.value)) return out.push(mk(rules, id, S, title, STATUS.REVIEW, keys, 'Subcontract value missing.'));
    if (s.listed_in_soq === true) return out.push(mk(rules, id, S, title, STATUS.NA, keys, 'Listed in the statement of qualifications, so excepted from § 22185.6(b). Subletting protections (§ 4100 et seq.) apply.'));
    if (!(s.value > t.threshold)) return out.push(mk(rules, id, S, title, STATUS.NA, keys, `At or below the ${money(t.threshold)} threshold.`));
    const miss = [];
    if (s.public_notice !== true) miss.push('public notice of the work');
    if (s.fixed_due_date_time !== true) miss.push('a fixed date and time for submissions');
    if (s.qualification_criteria !== true) miss.push('reasonable qualification criteria and standards');
    if (s.award_basis !== 'best_value') miss.push(`award on a best value basis (recorded: ${s.award_basis || 'none'})`);
    out.push(mk(rules, id, S, title, miss.length ? STATUS.FAIL : STATUS.PASS, keys,
      `Above the ${money(t.threshold)} threshold by ${money(s.value - t.threshold)}. ` + (miss.length ? `Missing: ${miss.join('; ')}.` : 'Public notice, criteria, and best value award are recorded.')));
  });
  return out;
}

// ---------------------------------------------------------------- workforce months

export function requiredGraduatePct(occupation, rules) {
  const occ = String(occupation || '').trim().toLowerCase();
  if (rule(rules, 'stw_exempt_occupations').value.includes(occ)) return null;
  if (rule(rules, 'stw_listed_occupations').value.includes(occ)) return rule(rules, 'stw_graduate_pct_listed_occupations').value;
  return rule(rules, 'stw_graduate_pct_default').value;
}

export function checkWorkforceMonths(rec, rules) {
  const out = [];
  const S = 'Skilled and trained workforce, monthly';
  const rows = rec.workforce_months;
  if (!Array.isArray(rows) || !rows.length) return out;
  const prime = rec.contract && isNum(rec.contract.total_value) ? rec.contract.total_value : null;
  const smallFrac = rule(rules, 'stw_small_sub_fraction').value;
  const minHrs = rule(rules, 'stw_min_monthly_hours').value;
  const mult = rule(rules, 'stw_withhold_multiplier').value;
  rows.forEach((m, i) => {
    const id = `STW-${i + 1}`;
    const title = `${m.contractor} · ${m.occupation} · ${m.month}`;
    if (m.report_submitted === false) {
      return out.push(mk(rules, id, S, title, STATUS.FAIL, 'stw_withhold_multiplier', 'No complete monthly report. The agency must withhold further payments until one is provided' + (isNum(m.monthly_billing) ? `; where a subcontractor caused the gap, the withholding is ${money(m.monthly_billing * mult)} (${mult * 100}% of its ${money(m.monthly_billing)} billing).` : '.'), 'Pub. Cont. Code § 2602(b)'));
    }
    const req = requiredGraduatePct(m.occupation, rules);
    if (req === null) return out.push(mk(rules, id, S, title, STATUS.NA, 'stw_exempt_occupations', 'The graduation percentage does not apply to teamster work.'));
    if (m.is_subcontractor && m.listed_subcontractor === false && prime !== null && isNum(m.subcontract_value) && m.subcontract_value <= prime * smallFrac) {
      return out.push(mk(rules, id, S, title, STATUS.NA, 'stw_small_sub_fraction', `Unlisted subcontract of ${money(m.subcontract_value)} does not exceed ${pct(smallFrac)} of the ${money(prime)} prime contract (${money(prime * smallFrac)}).`));
    }
    if (isNum(m.journeyperson_hours) && m.journeyperson_hours < minHrs) {
      return out.push(mk(rules, id, S, title, STATUS.NA, 'stw_min_monthly_hours', `${m.journeyperson_hours} journeyperson hours this month, under the ${minHrs}-hour floor.`));
    }
    const haveHead = isNum(m.journeypersons) && isNum(m.graduate_journeypersons) && m.journeypersons > 0;
    const haveHrs = isNum(m.journeyperson_hours) && isNum(m.graduate_hours) && m.journeyperson_hours > 0;
    if (!haveHead && !haveHrs) return out.push(mk(rules, id, S, title, STATUS.REVIEW, 'stw_graduate_pct_default', 'No headcount or hours data.'));
    const headPct = haveHead ? (m.graduate_journeypersons / m.journeypersons) * 100 : null;
    const hrsPct = haveHrs ? (m.graduate_hours / m.journeyperson_hours) * 100 : null;
    const ok = (headPct !== null && headPct >= req) || (hrsPct !== null && hrsPct >= req);
    const keys = req === rule(rules, 'stw_graduate_pct_default').value ? ['stw_graduate_pct_default'] : ['stw_graduate_pct_listed_occupations', 'stw_listed_occupations'];
    out.push(mk(rules, id, S, title, ok ? STATUS.PASS : STATUS.FAIL, keys,
      `Required ${req}% graduates. ` + (headPct !== null ? `By headcount ${m.graduate_journeypersons}/${m.journeypersons} = ${headPct.toFixed(1)}%. ` : '') + (hrsPct !== null ? `By hours ${m.graduate_hours}/${m.journeyperson_hours} = ${hrsPct.toFixed(1)}%. ` : '') +
      (ok ? 'Either test is enough (§ 2601(d)(4)).' : 'Neither test is met. The agency must withhold' + (isNum(m.monthly_billing) ? ` ${money(m.monthly_billing * mult)} (${mult * 100}% of the ${money(m.monthly_billing)} monthly billing)` : ` ${mult * 100}% of the monthly billing`) + ' until a compliance plan is provided, and forward the report to the Labor Commissioner (§ 2602(c)).')));
  });
  return out;
}

// ---------------------------------------------------------------- Legislature report

export function checkLegislatureReport(rec, rules, asOf) {
  const out = [];
  const S = 'Report to the Legislature';
  const due = rule(rules, 'legislature_report_due').value;
  const lr = rec.legislature_report || {};
  const awardDate = rec.dates && rec.dates.contract_award;
  if (lr.submitted === true) {
    const onTime = !isDate(lr.submitted_on) || lr.submitted_on <= due;
    out.push(mk(rules, 'LEG-1', S, `Report submitted by ${due}`, onTime ? STATUS.PASS : STATUS.FAIL, 'legislature_report_due', isDate(lr.submitted_on) ? `Submitted ${lr.submitted_on}.` : 'Recorded as submitted (no date).'));
  } else if (asOf > due) {
    out.push(mk(rules, 'LEG-1', S, `Report submitted by ${due}`, STATUS.FAIL, 'legislature_report_due', `As of ${asOf} the deadline has passed (${daysBetween(due, asOf)} days ago) and no report is recorded.`));
  } else {
    out.push(mk(rules, 'LEG-1', S, `Report submitted by ${due}`, STATUS.INFO, 'legislature_report_due', `Not yet submitted. ${daysBetween(asOf, due)} days remain from ${asOf}. It must go to the appropriate policy and fiscal committees, in compliance with Gov. Code § 9795.`));
  }
  if (isDate(awardDate) && awardDate > due) {
    out.push(mk(rules, 'LEG-2', S, 'Award after the report deadline', STATUS.REVIEW, 'legislature_report_due', `The award (${awardDate}) comes after the ${due} deadline. The statute sets a single report date and does not say how later projects are reported.`));
  }
  if (lr.contents) {
    const items = rule(rules, 'legislature_report_contents').value;
    const missing = items.filter((it) => lr.contents[it.key] !== true);
    out.push(mk(rules, 'LEG-3', S, 'Report covers all ten required items', missing.length ? STATUS.FAIL : STATUS.PASS, 'legislature_report_contents',
      missing.length ? `Missing ${missing.length} of ${items.length}: ` + missing.map((it) => `${it.label} (${it.citation})`).join('; ') + '.' : `All ${items.length} items are covered.`));
  }
  return out;
}

// ---------------------------------------------------------------- top level

export function validate(rec, rules, opts = {}) {
  const asOf = opts.asOf || rec.as_of;
  if (!isDate(asOf)) throw new Error('An as-of date (YYYY-MM-DD) is required: pass opts.asOf or set as_of in the record.');
  const findings = [
    ...checkAuthority(rec, rules, asOf),
    ...checkRfq(rec, rules),
    ...(rec.proposers || []).flatMap((p, i) => checkProposer(p, rules, i)),
    ...checkAwardAndBonds(rec, rules),
    ...checkGmpAndRetention(rec, rules),
    ...checkSubcontracts(rec, rules),
    ...checkWorkforceMonths(rec, rules),
    ...checkLegislatureReport(rec, rules, asOf),
  ];
  const counts = { PASS: 0, FAIL: 0, REVIEW: 0, INFO: 0, 'N/A': 0 };
  findings.forEach((f) => { counts[f.status] += 1; });
  return {
    as_of: asOf,
    agency: rec.agency && rec.agency.name,
    project: rec.project && rec.project.name,
    rules_verified_on: rules.meta.verified_on,
    counts,
    outcome: counts.FAIL ? 'gaps-found' : counts.REVIEW ? 'needs-review' : 'no-gaps-found',
    findings,
  };
}
