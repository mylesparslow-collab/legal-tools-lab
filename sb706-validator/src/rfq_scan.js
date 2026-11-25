// Keyword screen of a draft RFQ. It looks for wording that usually accompanies
// each required element and reports the first matching line as provenance.
// It is a reading aid: a hit does not mean the clause is adequate, and a miss
// does not mean the element is absent. No imports, no I/O.

export const RFQ_PATTERNS = [
  { key: 'project_description', citation: '§ 22185.3(a)(1)', label: 'Size, type, and design character', any: [/project description/i, /size,? type/i, /design character/i, /scope of (the )?project/i] },
  { key: 'expected_cost_range', citation: '§ 22185.3(a)(1)', label: 'Expected cost range', any: [/expected cost/i, /cost range/i, /estimated (project )?cost/i] },
  { key: 'evaluation_methodology', citation: '§ 22185.3(a)(1)', label: 'Evaluation methodology', any: [/methodology/i, /evaluat(e|ion) (of )?(the )?(statements|qualifications)/i, /how (statements|qualifications) will be evaluated/i] },
  { key: 'final_selection_procedure', citation: '§ 22185.3(a)(1)', label: 'Final selection procedure', any: [/final selection/i, /selection procedure/i] },
  { key: 'significant_factors', citation: '§ 22185.3(a)(2)', label: 'Significant evaluation factors', any: [/evaluation factors?/i, /significant factors?/i, /technical design/i] },
  { key: 'factor_weights', citation: '§ 22185.3(a)(3)', label: 'Factor weights', any: [/\bweights?\b/i, /relative importance/i, /\d+\s*(points|%|percent)/i] },
  { key: 'perjury_certification', citation: '§ 22185.3(a)(5)', label: 'Penalty of perjury certification', any: [/penalty of perjury/i] },
  { key: 'tpl_owners_listing', citation: '§ 22185.3(a)(4)(A)', label: 'Shareholders, partners, or members', any: [/shareholders?/i, /partners?,? or members/i] },
  { key: 'tpl_experience_and_financial', citation: '§ 22185.3(a)(4)(B)', label: 'Experience and financial statement', any: [/financial statement/i] },
  { key: 'tpl_licenses', citation: '§ 22185.3(a)(4)(C)', label: 'Licenses and any revocation or suspension', any: [/licen[sc]es?/i] },
  { key: 'tpl_bonding_insurance_capacity', citation: '§ 22185.3(a)(4)(D)', label: 'Bonding and insurance capacity', any: [/payment and performance bond/i, /errors and omissions/i, /bonding capacity/i] },
  { key: 'tpl_workers_comp_safety_program', citation: '§ 22185.3(a)(4)(E)', label: 'Workers’ compensation history and safety program', any: [/workers[’'] compensation/i, /safety program/i] },
  { key: 'tpl_org_documents', citation: '§ 22185.3(a)(4)(F)', label: 'Organizational documents', any: [/organizational documents?/i, /agreement committing to form/i] },
  { key: 'tpl_safety_record', citation: '§ 22185.3(a)(4)(G)', label: 'Safety record', any: [/experience modification/i, /\bEMR\b/, /recordable (injury|incident)/i, /safety record/i] },
  { key: 'stw_commitment', citation: '§ 22185.3(b)', label: 'Skilled and trained workforce commitment', any: [/skilled and trained workforce/i, /project labor agreement/i] },
  { key: 'coi', citation: '§ 22185.2', label: 'Organizational conflict of interest', any: [/conflicts?[- ]of[- ]interest/i] },
];

export function scanRfqText(text) {
  const lines = String(text).split(/\r?\n/);
  return RFQ_PATTERNS.map((p) => {
    for (let i = 0; i < lines.length; i += 1) {
      const re = p.any.find((r) => r.test(lines[i]));
      if (re) return { key: p.key, label: p.label, citation: p.citation, found: true, line: i + 1, excerpt: lines[i].trim().slice(0, 160) };
    }
    return { key: p.key, label: p.label, citation: p.citation, found: false, line: null, excerpt: null };
  });
}
