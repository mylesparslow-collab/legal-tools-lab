# Corrections to the research report (Tool 12)

The report's Tool 12 section was checked on 2026-11-25 against leginfo, the Judicial Council's
Appendix H, the OEHHA list dated 2026-07-31, and Cornell LII's mirror of title 27 of the
California Code of Regulations. Verification status for each rule is in `rules/prop65_rules.json`.

## Where the report is wrong or incomplete

- **The 14-day cure penalty is $610, not $500.** $500 is the base figure in Health & Saf. Code § 25249.7(k)(2)(B)(i). The Judicial Council adjusts it every five years, and Cal. Rules of Court, Appendix H sets it at $610 per facility for the period starting April 1, 2024. The next adjustment is April 1, 2029.
- **The cure is not a general "premises cure".** § 25249.7(k) covers four exposures only: alcohol consumed on the premises, chemicals formed by cooking in food prepared and sold on the premises, tobacco smoke where smoking is permitted, and engine exhaust in a parking facility. It can be used once per exposure per facility (subd. (m)), requires a written proof of compliance, and the penalty must be delivered within 30 days of service.
- **The 12-month grace period runs to the exposure, not the purchase.** § 25249.10(b) exempts an exposure that takes place less than twelve months after listing. The report tests the purchase date. A chemical listed for several endpoints on different dates has a separate clock for each.
- **Safe harbor math needs an intake rate for average users.** The report describes ppm or ppb times daily intake. 27 CCR §§ 25721(d)(4) and 25821(c)(2) require the reasonably anticipated intake of average users of the product, not a per capita figure. The defendant carries the burden (§ 25249.10(c)), and a chemical with no listed level is not presumed unsafe (27 CCR §§ 25701(c), 25801(d)).
- **The short-form transition turns on the manufacture and label date.** Under 27 CCR § 25603(c) the old short form may stay on a product manufactured and labeled before January 1, 2028, whenever it is sold. The report describes only a three-year transition.
- **Food short-form warnings are in a different section.** The report cites §§ 25602-25603. Food content is in 27 CCR § 25607.2(b), uses www.P65Warnings.ca.gov/food, and does not list the triangle symbol.
- **The fee standard is not stated as CCP § 1021.5 in the statute.** § 25249.7(f)(4)(B) requires the court to find the fee award reasonable under California law. The Attorney General's settlement guidelines (11 CCR §§ 3200-3204) were not read for this build.
- **The under-10-employee exemption is missing from the report.** § 25249.11(b) excludes businesses with fewer than 10 employees and government entities. It is the cheapest check to run on a new notice.
- **The 60-day clock has a mail extension.** Under 27 CCR § 25903(d) the sixty days run from service as computed under CCP § 1013, which adds 5 days for mail inside California and 10 for mail to or from another state.
- **Welf. & Inst. Code § 15600 is only the findings section.** The enhanced elder abuse remedies are in § 15657, which was amended effective January 1, 2026 (AB 251) to add a preponderance path through § 15657.02.
- **Civ. Code § 2860 does not say a misquoted endorsement forfeits independent counsel.** The statute requires an express written waiver. The report's forfeiture point is not in the text.
- **The OAG export is not limited to 1,000 rows.** The on-screen search shows at most 1,000 notices per query. The CSV export returned every row for each two-week window requested (166 windows, 30,108 notices, no errors). The same settlement is repeated under each notice it resolves, so raw rows overcount payments.

## Where the report checks out

- Health & Saf. Code § 25249.7(d) for the 60-day notice and certificate of merit.
- 27 CCR §§ 25705 and 25805 as the homes of the NSRL and MADL tables.
- Short-form amendments operative January 1, 2025, with a named chemical required in the new form.
- The Attorney General's notice search exports CSV to a plain HTTP client. OEHHA's site turned away a scripted request from this build and its list was read in a browser instead.

## Not verified

- 11 CCR §§ 3200-3204 (Attorney General settlement guidelines), 27 CCR § 25501 (naturally occurring chemicals), 27 CCR § 25601(c) (short-form type size relative to other label text), 27 CCR § 25707 (routes of exposure), CCP § 135 (judicial holidays), Welf. & Inst. Code § 15657.02.
- Title 27 was read on the LII mirror, not on the official Westlaw-hosted CCR.
- The cure penalty amount in effect before April 1, 2024.
