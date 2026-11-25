# Corrections to the research report (Tool 4 section)

Checked on 2026-11-25 against the statute text on leginfo.legislature.ca.gov, HCAI Policy Intent Notice 80 (effective 3/4/2025), IRS Rev. Proc. 2017-13, the State Bar's Rules of Professional Conduct, and the CalHHS open data API. Not legal advice.

## 1. Wrong section

**Report says:** AB 869's delay is at 'HSC § 130066.5'.

**Source says:** AB 869 (Stats. 2024, ch. 801) amended § 130065 and added §§ 130065.1, 130065.15, 130078.5 and 130078.6. The delay is § 130065.1. Section 130066.5 is the AB 1882 (Stats. 2022, ch. 584) public-notice and annual status-update section.

**Checked against:** leginfo: HSC §§ 130065.1, 130066.5; AB 869 bill status

## 2. Incomplete

**Report says:** The extensions run to 2033.

**Source says:** § 130065.1(b) allows a delay of up to three years (January 1, 2033). § 130065.1(e) lets HCAI add up to two more years, with an outer limit of January 1, 2035 (§ 130065.1(g)). PIN 80 says the additional delay will not be considered before January 1, 2030.

**Checked against:** leginfo: HSC § 130065.1; HCAI PIN 80 p. 6

## 3. Incomplete

**Report says:** The extensions are for 'distressed/rural/district hospitals'.

**Source says:** Five categories qualify: Distressed Hospital Loan Program recipients, small hospitals (50 beds or fewer), rural hospitals, critical access hospitals and health care district hospitals. Hospitals in integrated systems with two or more separately licensed hospitals are excluded unless the whole system is in financial distress or one of three exceptions in § 130065.1(c)(2) applies.

**Checked against:** leginfo: HSC § 130065.1(a)-(c)

## 4. Not in source

**Report says:** The tool reads 'PIN 80 Quarterly Progress Reports'.

**Source says:** PIN 80 has no quarterly progress report. Milestone status is updated at least once a year, the plan is updated annually or when it changes, and hospitals relying on system financial distress file financial status reports each February 1 and August 1.

**Checked against:** HCAI PIN 80 (eff. 3/4/2025) pp. 5, 8

## 5. Not in source

**Report says:** Milestone slippage threatens 'AB 869 extension tolling'.

**Source says:** Neither § 130065.1 nor PIN 80 uses a tolling concept. A missed schedule or major milestone carries a fine of $5,000 per calendar day (§ 130065.1(g); PIN 80 applies it per facility, to critical milestones only) and a hold on building permits other than seismic, maintenance and emergency repair work (§ 130065.1(i)). HCAI may adjust the schedule on a request made at least 30 calendar days before the milestone date.

**Checked against:** leginfo: HSC § 130065.1(g), (i); HCAI PIN 80 pp. 9-10

## 6. Overstated

**Report says:** January 1, 2030 is a 'shut-down cliff' under § 130065.

**Source says:** § 130065(a) requires owners to demolish, replace, change to nonacute use, or retrofit noncompliant acute care buildings by January 1, 2030. § 130065(b) itself recognizes approved delays of 'up to three years or, at most, five years'. The report also omits SB 1447 (Stats. 2024, ch. 896), which amended § 130065 and added § 130069.1 for Children's Hospital Los Angeles.

**Checked against:** leginfo: HSC §§ 130065, 130069.1

## 7. Confirmed

**Report says:** Governor Newsom vetoed SB 1432.

**Source says:** Confirmed. SB 1432 (2023-24) was vetoed on September 12, 2024. It would have let any hospital apply for up to a five-year extension.

**Checked against:** leginfo: SB 1432 bill status and veto message

## 8. Misapplied

**Report says:** Shared-savings splits must 'satisfy IRS Rev. Proc. 2017-13 private-business-use caps' when tax-exempt bonds fund the tower.

**Source says:** Rev. Proc. 2017-13 is a safe harbor for management contracts. Section 4.03 says a management contract 'does not include a contract or portion of a contract for the provision of services before a managed property is placed in service (for example, pre-operating services for construction design or construction management)'. It contains no percentage cap on shared savings; its conditions concern net-profit and net-loss sharing from operations, contract term, owner control and similar points. The engine applies no such cap. It records whether the project is bond-financed and raises a question for bond counsel only if the contract scope includes services after the building is placed in service.

**Checked against:** irs.gov: Rev. Proc. 2017-13 §§ 4.03, 5

## 9. Overstated

**Report says:** The tool embeds 'mandatory CRPC Rule 4.3 non-representation checks on every Joining Agreement'.

**Source says:** Rule 4.3 exists and governs what a lawyer may say to a person who has no counsel. It does not mention joining agreements or require a check. The engine keeps a counsel-status field on each joining record as a workflow control and labels it that way.

**Checked against:** calbar.ca.gov: Rules of Professional Conduct, ch. 4, rule 4.3

## 10. Partly confirmed

**Report says:** HCAI Hospital Building Seismic Data is 'live biweekly' with Perm ID, SPC Rating and AB 1882 Notice.

**Source says:** The resource ID is live (4,714 rows, last modified November 16, 2026) and those three columns exist. The update frequency is not stated in the resource metadata, so 'biweekly' is unconfirmed. The export has no NPC rating column, and compliance requires NPC 5 as well, so NPC ratings have to come from the hospital's own records. The Rural Hospitals resource ID is also live (359 rows) with Rural, CAH, LicensedBeds and AcuteBeds columns.

**Checked against:** data.chhs.ca.gov CKAN API: resource_show and datastore_search

## 11. Contract-specific

**Report says:** Overruns 'exhaust Shared Contingency and 100% of the team's ICL prior to touching Owner contingency up to any EMP, while preserving direct reimbursable Limb-1 costs'.

**Source says:** This is one possible negotiated arrangement, not a general rule. Howard Ashcraft's published description of the IPD model has the owner paying variable costs with no cap and the parties' profit fully at risk; it does not use the terms ICL, EMP or 'Limb-1' ('limb' terminology comes from alliance contracts). No actual IFOA was available to check. The engine takes the tier order, savings split and cap from the ledger file.

**Checked against:** Ashcraft, 'Integrated Project Delivery Agreement - A Lawyer's Perspective' (2014), hansonbridgett.com

## 12. Not verified

**Report says:** Cal-Mortgage bonds are rated 'AA-'; project sizes and attorney names.

**Source says:** Not checked. None of these feed the engine.

**Checked against:** none
