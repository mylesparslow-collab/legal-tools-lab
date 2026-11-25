"""Writes sample_data/. Every name, fund, person, dollar figure and clause is invented."""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sample_data")

FUND = {
    "name": "Harbor Crest Capital Partners V, L.P. (fictional)",
    "general_partner": "Harbor Crest GP V, LLC (fictional)",
    "fund_type": "private_equity",
    "subscription_date": "2026-10-30",
    "final_closing_date": "2026-11-13",
    "compendium_delivery_date": "2026-11-16",
    "mfn_terms": {
        "clause_ref": "LPA § 14.6 (fictional)",
        "election_window_days": 20,
        "day_type": "calendar",
        "roll_forward_if_weekend": True,
        "aggregate_affiliates": True,
        "excluded_categories": ["lpac_seat", "transfer"],
    },
    "placement_agents": [
        {"name": "Dana Whitlock", "firm": "Bluewater Placement Advisors LLC", "claims_exemption": None},
        {"name": "Marcus Oyelaran", "firm": "Bluewater Placement Advisors LLC", "claims_exemption": None},
        {"name": "Priya Venkataraman", "firm": "Harbor Crest Management LLC", "claims_exemption": "82047.3(b)"},
    ],
}

INVESTOR_STATE = {
    "name": "Redwood State Public Employees' Retirement Fund (fictional)",
    "system_type": "state",
    "commitment": 85000000,
    "affiliates": [{"name": "Redwood State Retiree Health Benefit Trust (fictional)", "commitment": 40000000}],
    "statuses": ["governmental_plan", "public_records", "sovereign", "tax_exempt", "state_entity:California"],
    "admitted_at_initial_closing": False,
}
INVESTOR_COUNTY = {
    "name": "Tule County Employees' Retirement Association (fictional 1937 Act system)",
    "system_type": "local",
    "commitment": 60000000,
    "affiliates": [],
    "statuses": ["governmental_plan", "public_records", "tax_exempt", "state_entity:California"],
    "admitted_at_initial_closing": False,
}

REGISTRY = [
    ("L-90411", "Dana Whitlock", "Bluewater Placement Advisors LLC", "Active", "2025-2026"),
    ("L-90377", "Jonah Reyes-Albright", "Bluewater Placement Advisors LLC", "Active", "2025-2026"),
    ("L-88102", "Helen Akintola", "Stonebridge Capital Introductions LP", "Terminated", "2025-2026"),
    ("L-91530", "Wendell Kovacs", "Kovacs Public Affairs", "Active", "2025-2026"),
]

SIDE_LETTER = """SIDE LETTER (DRAFT - FICTIONAL)

Harbor Crest GP V, LLC (the "General Partner"), as general partner of Harbor Crest Capital Partners V, L.P. (the "Fund"), agrees with the undersigned investor (the "Investor") as follows. Capitalized terms not defined here have the meanings given in the Fund's limited partnership agreement (the "Partnership Agreement").

1. Commitment. The Investor has subscribed for a Commitment of $85,000,000. For purposes of Section 14.6 of the Partnership Agreement, the Commitment of the Investor shall be aggregated with the Commitments of its Affiliates.

2. Fee Reporting. The General Partner shall use commercially reasonable efforts to provide the Investor, annually, with the information described in California Government Code Section 7514.7, including the Investor's pro rata share of fees and expenses paid from the Fund to the General Partner and the Investor's pro rata share of carried interest distributed to the General Partner. The General Partner shall provide such information solely to the extent it is tracked by the General Partner in the ordinary course and can be provided without incremental expense to the General Partner or the Fund.

3. Public Records. The General Partner acknowledges that the Investor is subject to public records laws, including California Government Code Section 6254.26. The Investor may disclose the name and vintage year of the Fund, the amount of the Investor's Commitment, the amount of the Investor's contributions and distributions, and the net internal rate of return of the Fund; provided that, before making any such disclosure, the Investor shall obtain the prior written consent of the General Partner and deliver to the General Partner an opinion of counsel that the disclosure is required by law.

4. Placement Agents. The General Partner has engaged Bluewater Placement Advisors LLC as placement agent in connection with the offer of Interests to the Investor, acting through Dana Whitlock and Marcus Oyelaran. The placement agent will receive a fee equal to 1.5% of the Investor's Commitment, payable upon the admission of the Investor to the Fund. No portion of such fee shall be borne by the Investor.

5. Indemnification. The Investor shall indemnify the General Partner and the Fund against any losses arising from a breach of the Investor's representations in its subscription agreement, without limitation as to amount.

6. Governing Law; Forum. This letter is governed by the laws of the State of Delaware. The Investor submits to the exclusive jurisdiction of the courts of the State of Delaware, waives any immunity from suit or enforcement to which it may be entitled, and waives any right to a trial by jury.

7. LPAC Observer. For so long as the Investor holds its Interest, the Investor may designate one non-voting observer to attend meetings of the Advisory Committee.

8. Most Favored Nation. Within 20 days after the General Partner delivers the compendium of side letter provisions under Section 14.6 of the Partnership Agreement, the Investor may elect the benefit of any provision granted to a Limited Partner whose Commitment is equal to or less than the Investor's Commitment, subject to the exceptions in that Section.
"""

# (lead-in, body). Thirty-six provisions, three to a page.
PROVISIONS = [
    ("Granted to one or more Limited Partners.", "The General Partner shall deliver the Fund's audited annual financial statements within 120 days after the end of each fiscal year, and shall include in each annual report a schedule of all fees and expenses charged to the Fund."),
    ("Granted to a Limited Partner with a Commitment of at least $50,000,000.", "The Management Fee payable by the Limited Partner shall be reduced by 10 basis points per annum during the Commitment Period."),
    ("Granted to a Limited Partner with a Commitment of at least $100,000,000.", "The Management Fee payable by the Limited Partner shall be reduced by 25 basis points per annum during the Commitment Period and by a further 10 basis points per annum after the Commitment Period ends."),
    ("Granted to a Limited Partner with a Commitment of at least $250,000,000.", "The Management Fee payable by the Limited Partner shall be reduced by 40 basis points per annum for the life of the Fund."),
    ("Granted to a Limited Partner that is subject to ERISA.", "The General Partner shall use reasonable best efforts to conduct the Fund's affairs so that the assets of the Fund are not treated as plan assets, and shall deliver an annual certificate to that effect."),
    ("Granted to a Limited Partner that is a governmental plan.", "The General Partner acknowledges that the Limited Partner is not subject to Title I of ERISA and agrees that no representation in the Subscription Agreement shall be read to say otherwise."),
    ("Granted to a Limited Partner that is subject to public records laws.", "The General Partner agrees that the Limited Partner may disclose, without notice to or consent of the General Partner, the name, address and vintage year of the Fund, the amount of its Commitment, its contributions and distributions, the remaining value of its Interest, the Fund's net internal rate of return and investment multiple, the management fees and costs it has paid, and the cash profit it has received."),
    ("Granted to a Limited Partner that is subject to the Bank Holding Company Act.", "The Limited Partner's Interest shall be treated as a non-voting interest to the extent it exceeds 4.99% of the voting Interests of the Fund."),
    ("Granted to a Limited Partner with a Commitment of at least $100,000,000.", "The General Partner shall offer the Limited Partner the opportunity to co-invest, without management fee or carried interest, in each co-investment opportunity that the General Partner makes available to Limited Partners generally, in priority to third parties."),
    ("Granted to a Limited Partner with a Commitment of at least $250,000,000.", "The General Partner shall offer the Limited Partner a pro rata share of every co-invest opportunity exceeding $25,000,000 before offering it to any other person."),
    ("Granted to a Limited Partner with a Commitment of at least $100,000,000.", "The Limited Partner may appoint one member to the Advisory Committee for so long as it holds its Interest."),
    ("Granted to a Limited Partner with a Commitment of at least $50,000,000.", "The Limited Partner may designate one non-voting observer to attend each meeting of the Advisory Committee and to receive all materials delivered to its members."),
    ("Granted to one or more Limited Partners.", "If a Key Person Event occurs and is continuing for 90 days, the Limited Partner may, by notice to the General Partner, decline to fund any capital call for a new Portfolio Investment until the Advisory Committee approves a replacement."),
    ("Granted to a Limited Partner with a Commitment of at least $100,000,000.", "The General Partner shall notify the Limited Partner within five Business Days if any Key Person devotes less than substantially all of that person's business time to the Fund and its predecessor funds."),
    ("Granted to a Limited Partner that is an instrumentality of the State of Texas.", "The General Partner acknowledges that the Limited Partner may be excused from any Portfolio Investment that would cause it to violate Chapter 809 of the Texas Government Code."),
    ("Granted to one or more Limited Partners.", "The Limited Partner shall be excused from participating in any Portfolio Investment in a company that, at the time of investment, is the subject of sanctions administered by the Office of Foreign Assets Control."),
    ("Granted to a Limited Partner that is a governmental plan or is subject to public records laws.", "The Limited Partner shall be excused from any Portfolio Investment that its governing board determines, in a written policy delivered to the General Partner before the Final Closing, to be prohibited to it."),
    ("Granted to a Limited Partner admitted at the Initial Closing.", "The Management Fee payable by the Limited Partner shall be reduced by 15 basis points per annum for the first two years of the Commitment Period."),
    ("Granted to a Limited Partner that is an Affiliate of the General Partner.", "No Management Fee and no Carried Interest shall be payable in respect of the Limited Partner's Interest."),
    ("Granted to a Limited Partner with a Commitment of at least $50,000,000.", "The General Partner shall provide, with each quarterly report, the Limited Partner's pro rata share of fees and expenses paid from the Fund to the General Partner and its related parties, and of all fees paid by portfolio companies to the General Partner and its related parties, in the reporting template published by the Institutional Limited Partners Association."),
    ("Granted to one or more Limited Partners.", "The General Partner shall provide the Limited Partner, annually and without qualification as to cost, the Limited Partner's pro rata share of Carried Interest distributed to the General Partner and its related parties."),
    ("Granted to a Limited Partner that is a non-U.S. investor.", "The General Partner shall use commercially reasonable efforts to structure Portfolio Investments so that the Limited Partner does not recognise income effectively connected with a United States trade or business."),
    ("Granted to a Limited Partner that is tax-exempt.", "The General Partner shall use commercially reasonable efforts to minimise unrelated business taxable income and shall report the amount of any UBTI allocated to the Limited Partner each year."),
    ("Granted to a Limited Partner that is an insurance company.", "The General Partner shall provide the information the Limited Partner reasonably requests to complete its statutory filings with its state insurance regulator."),
    ("Granted to a Limited Partner with a Commitment of at least $100,000,000.", "The Limited Partner may Transfer all of its Interest to an Affiliate without the consent of the General Partner, on ten days' notice."),
    ("Granted to a Limited Partner that is entitled to sovereign immunity.", "Nothing in the Partnership Agreement or the Subscription Agreement shall be a waiver of any immunity to which the Limited Partner is entitled, and the Limited Partner does not submit to the exclusive jurisdiction of any court outside its home state."),
    ("Granted to a Limited Partner that is a governmental plan.", "The Limited Partner's obligation to indemnify the Fund under the Subscription Agreement shall apply only to the extent permitted by the law that governs the Limited Partner and shall not exceed its unfunded Commitment."),
    ("Granted to one or more Limited Partners.", "The General Partner represents that it has disclosed every placement agent engaged in connection with the Limited Partner's investment and all compensation paid or payable to each of them, and shall comply with the Limited Partner's placement agent policy."),
    ("Granted to a Limited Partner with a Commitment of at least $250,000,000.", "The Preferred Return applicable to the Limited Partner's Interest shall be 9% per annum rather than 8% per annum."),
    ("Granted to one or more Limited Partners.", "The General Partner shall hold an annual meeting of Limited Partners and shall make the Key Persons available at that meeting."),
    ("Granted to certain Limited Partners in the amounts agreed with the General Partner.", "The General Partner shall waive up to $2,000,000 of organisational expenses otherwise allocable to the Limited Partner."),
    ("The General Partner confirms, for a Limited Partner with a Commitment of $75,000,000, that", "capital calls shall be made on not less than twelve Business Days' notice."),
    ("Granted to a Limited Partner with a Commitment of at least $50,000,000.", "The General Partner shall give the Limited Partner prompt written notice of any clawback obligation of the General Partner and of the amount held in escrow against it."),
    ("Granted to a Limited Partner that is subject to public records laws.", "The General Partner shall mark as confidential any document it considers a trade secret before delivering it, and agrees that unmarked Confidential Information may be treated by the Limited Partner as disclosable."),
    ("Granted to a Limited Partner that is a public pension plan of the State of Oregon.", "The General Partner consents to the jurisdiction of the courts of the State of Oregon for any claim brought by the Limited Partner."),
    ("Granted to a Limited Partner with a Commitment of at least $100,000,000.", "The General Partner shall deliver quarterly a schedule of each Portfolio Investment's cost and fair value, and shall report any change in valuation methodology."),
]


def compendium_text():
    lines = ["MFN COMPENDIUM OF SIDE LETTER PROVISIONS (FICTIONAL)", "Harbor Crest Capital Partners V, L.P.", ""]
    for i, (lead, body) in enumerate(PROVISIONS):
        if i % 3 == 0:
            lines += [f"--- Page {i // 3 + 1} ---", ""]
        lines += [f"Provision {i + 1}. {lead} {body}", ""]
    return "\n".join(lines)


# Stand-in for a model's output. Two items are good (one moves provision 30 out of the keyword rule's category); three are bad on purpose and must be rejected.
MODEL_OUTPUT = [
    {"provision_id": 30, "page": 10, "category": "other", "quote": "shall hold an annual meeting of Limited Partners", "note": "An annual-meeting covenant, not a key-person trigger."},
    {"provision_id": 36, "page": 12, "category": "reporting", "quote": "shall report any change in valuation methodology", "note": "Quarterly valuation schedule."},
    {"provision_id": 2, "page": 1, "category": "management_fee", "quote": "reduced by 50 basis points per annum", "note": "Fabricated figure; the text says 10."},
    {"provision_id": 9, "page": 4, "category": "co_investment", "quote": "opportunity to co-invest", "note": "Wrong page; provision 9 is on page 3."},
    {"provision_id": 13, "page": 5, "category": "best_terms", "quote": "Key Person Event", "note": "Category not in the fixed list."},
]


def main():
    os.makedirs(OUT, exist_ok=True)
    w = lambda n, o: json.dump(o, open(os.path.join(OUT, n), "w", encoding="utf-8"), indent=2)
    w("fund.json", FUND)
    w("investor_state.json", INVESTOR_STATE)
    w("investor_county.json", INVESTOR_COUNTY)
    w("model_output.json", MODEL_OUTPUT)
    open(os.path.join(OUT, "draft_side_letter.txt"), "w", encoding="utf-8").write(SIDE_LETTER)
    open(os.path.join(OUT, "mfn_compendium.txt"), "w", encoding="utf-8").write(compendium_text())
    with open(os.path.join(OUT, "lobbyist_registry_snapshot.csv"), "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["registry_id", "lobbyist_name", "firm", "status", "session"])
        wr.writerows(REGISTRY)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
