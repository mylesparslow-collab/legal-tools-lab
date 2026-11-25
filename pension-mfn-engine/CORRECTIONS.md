# Corrections to the research report (Tool 9)

Each section below was read on leginfo.legislature.ca.gov on November 25, 2026. The report is the Gemini-written "Legal Tools Deep Research" document dated November 24, 2026. I am not an attorney; these are differences between the report and the statutory text, not legal conclusions.

| # | Report says | Primary text says | Effect on the build |
|---|---|---|---|
| 1 | Gov. Code § 7514.7 "requires GPs to make reasonable efforts to report" fees, carry and expenses. | § 7514.7(a): the public investment fund "shall require each alternative investment vehicle in which it invests to make the following disclosures at least annually". "Reasonable efforts" appears only in (d)(2), for pre-2017 contracts with no new commitment, and it is the public fund's duty. | "Reasonable efforts" in a fee-reporting clause is a flag, not the standard. Pre-2017 contracts go to review. |
| 2 | Tool covers PE, private credit, infrastructure and real-estate funds. | § 7514.7(c)(1) and § 7928.710(a)(1) define "alternative investment" as a private equity, venture, hedge or absolute return fund. | For any other fund type the engine returns "review: outside the named definition" for those two sections and does not screen. |
| 3 | § 7928.710 mandates disclosure of "fund name, vintage, commitment size, aggregate distributions, and IRR". | § 7928.710(c) lists nine items. Missing from the report: cash contributions, distributions plus remaining value, investment multiple, management fees and costs paid, cash profit received. | The gate checks all nine by name. |
| 4 | LPA confidentiality clauses "must allow statutory disclosure without requiring prior GP consent or a formal opinion of counsel". | § 7928.710 does not mention consent or opinions of counsel. | Kept as a screening flag, labelled as a drafting position that needs attorney judgment. |
| 5 | "§§ 7513.8, 7513.85 (AB 1743 Placement Agents as Lobbyists)". | § 7513.85 was added by AB 1584 (Stats. 2009, ch. 301). AB 1743 (Stats. 2010, ch. 668) added § 7513.86, which is the lobbyist registration rule. § 7513.8 is definitions. | Rules cite § 7513.86 for registration. |
| 6 | "mandates FPPC lobbyist registration (§ 82039(b))". | Placement agents are lobbyists under § 82039(a)(2). § 82039(b) is an exclusion ("An individual is not a lobbyist by reason of activities described in Section 86300"). | Citation corrected. |
| 7 | "enforces 5-year solicitation bans for violations (§ 7513.85)", listed with the contingent-fee and registration rules. | § 7513.85(b): the five-year bar follows a violation of the board's placement-agent disclosure policy, and the board may reduce it by majority vote for good cause. | Not modelled as a penalty for the lobbyist rules. The gate instead checks for the written agreement to comply with the policy that § 7513.85(c) requires. |
| 8 | Title groups CalPERS, CalSTRS and 1937 Act systems under the same placement-agent rules. | § 7513.86 and the § 86205(f) contingent-fee bar reach placement agents for a "state public retirement system" (§§ 82047.3, 82002(a)(2)). For a local system § 7513.87 points to local lobbying rules. | The engine takes the system type as an input. State-only rules return "not applicable" for a county system, and § 7513.87 becomes a manual review item. |
| 9 | Art. XVI § 6 "bars unlimited public-fund indemnification". | The section restricts lending of public credit and gifts of public money. It does not mention indemnification. | Marked interpretive. Uncapped indemnities are flagged for an attorney with no statement about the law. |
| 10 | "sovereign immunity" as a mandatory checklist item, no citation. | Nothing to verify. | Marked unverified. Immunity, forum and jury waivers are flagged for an attorney only. |
| 11 | "20-day post-closing MFN election sprints"; tiers of $50M, $100M, $250M+. | Not statutory. These are fund-agreement terms. | Window length, day-count, weekend roll-forward, affiliate aggregation and carve-outs are read from the fund file; tier thresholds are read from each provision's text. |

Not in the report, added after reading the code sections:

* § 7513.9: a placement agent must disclose to the board campaign contributions and gifts over the prior 24 months.
* § 82047.3(b), (c): two exemptions from "placement agent" (an employee who spends a third or more of their time managing assets; a registered manager in a competitive bid that accepts a fiduciary standard). A claimed exemption goes to review.

Not verified in this build:

* Which systems count as a "state public retirement system" (the defining section was not found).
* That § 6254.26 is the predecessor of § 7928.710. The current section's history note says it has been operative since January 1, 2023; the old number was not re-read.
* The Cal-Access lobbying site (https://cal-access.sos.ca.gov/Lobbying/) loads and has placement-agent filing pages, but the engine does not query it. The registry check runs against a synthetic CSV.
