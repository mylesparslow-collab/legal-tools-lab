# Corrections to the research report (Tool 7)

The report's Tool 7 section was checked against the current text on
leginfo.legislature.ca.gov on 2026-11-25. Section numbers and the effective date were
right. Several descriptions of what the sections say were not.

| # | Report said | Primary text | Effect on the build |
|---|---|---|---|
| 1 | One protest per parcel is enforced by "Art. XIII D § 6(a)(2)". | § 6(a)(2) only says a majority of owners of the identified parcels. The one-protest-per-parcel rule, and the owner-or-tenant wording, are in Gov. Code § 53755(b). | Dedupe cites § 53755(b). |
| 2 | Gov. Code § 53755 is the basis for joining parcel rolls with billing accounts. | § 53755(a) lets the agency give notice in the billing statement. It does not address matching. | The join is described as a practical step, not a statutory one. |
| 3 | The threshold is "50% + 1". | "A majority of owners of the identified parcels." With an odd number of parcels, 50% + 1 is too high (101 parcels: majority is 51, not 51.5). The denominator is all identified parcels, not protests received. | Threshold is floor(N/2)+1. |
| 4 | Count "a parcel once even if co-owners and tenants submit multiple protest cards, while applying proportional financial-obligation weighting on § 4 special assessments." | These are two different tests. § 6 fees: one protest per parcel, majority of parcels. § 4 assessments: ballots opposed vs. ballots in favor, weighted by dollars, among ballots returned (§ 4(e)). Co-owner ballots under § 4 are not collapsed to one; the parcel's amount is allocated among them by record interest (Gov. Code § 53753(e)(3)). Ballots can be changed or withdrawn before testimony closes (§ 53753(c)). | Two separate tallies. |
| 5 | The agency must give "≥ 45-day notice of the exhaustion requirement". | Two 45-day periods: the proposed fee must be public at least 45 days before the objection deadline (§ 53759.1(c)(1)), and the deadline must be at least 45 days after the Prop 218 notice (c)(4). The notice must carry a prominent statement (c)(6). | Both periods are checked. |
| 6 | (Omitted.) | The agency must also post a written basis for the fee on its website, link it in the notice, and mail it on request (§ 53759.1(c)(2)-(3)). | Added as checks. |
| 7 | The agency "adopts" responses; the gate ends in a "Board Resolution Exhibit". | The agency "considers and responds in writing" before the hearing closes, and the objections and responses must be "presented to the local agency's governing body for consideration prior to or during" the hearing (c)(5). Nothing requires adoption or a resolution exhibit. | Gate checks response date and presentation to the board. An exhibit reference is optional. |
| 8 | Missing one timely objection "destroys the statutory shield". | Not stated. Subdivision (c) says the requirement "applies only if the local agency does all of the following"; subdivision (e) says there is no independent cause of action over the adequacy of a response. The consequence of one miss is an open question. | Gate is a conservative control. README lists this for attorney review. |
| 9 | A ratepayer who did not object "is statutorily barred from suing". | The bar covers actions "alleging noncompliance with Article XIII D", and the objection must specify the grounds (§ 53759.1(b)). Suits over how an adopted fee is implemented are preserved (§ 53759.2(c)). | Wording in the tool is narrower. |
| 10 | Court review is "strictly confined to the administrative record". | Limited to the record "except as provided in paragraph (2)", which lists five exceptions: standing, affirmative defenses, completeness of the record, compliance with § 53759.1(c), and evidence needed to explain the record (§ 53759.2(b)(2)(A)-(E)). | Record index notes the exceptions. |
| 11 | Responses are "§ 53759.1(c) response paragraphs". | The response duty is § 53759.1(c)(5). | Citation fixed. |
| 12 | Scope is "a water or sewer agency"; the practice description also lists solid waste. | "Fee or assessment" means a property-related water or sewer fee or charge, or any special assessment (§ 53759.1(a)(2)). Sewer includes storm water works. Refuse collection fees are not in the definition. | Scope check fails a refuse fee. |
| 13 | Peaking factors named with no citation. | Gov. Code § 53750.6 (AB 1827, effective Jan. 1, 2025). | Added as an issue tag. |

Confirmed as stated: AB 2257 is Stats. 2024, ch. 561, effective Jan. 1, 2025, adding
§§ 53759.1 and 53759.2. The 120-day limit is Gov. Code § 53759(a) (SB 323, effective
Jan. 1, 2022), running from the later of the effective date and adoption, for fees
adopted after Jan. 1, 2022; the notice must mention it (§ 53759(d)). Hydrant costs
are § 53750.5 (SB 1386).

Not checked: the two cases the report names (Capistrano Taxpayers, Coziahr), and the
report's statements about firm practices and economics.
