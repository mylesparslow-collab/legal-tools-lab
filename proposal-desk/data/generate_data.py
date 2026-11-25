"""Generate the synthetic library used by the demo. Seeded: same output every run.

Everything here is invented. The firm, agencies, people and matters do not exist.
Run:  python data/generate_data.py
Writes JSON files into data/library/.
"""
import datetime as dt
import json
import os
import random

SEED = 20261125
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library")

# ------------------------------------------------------------------ firm facts

FIRM_FACTS = {
    "as_of": "2026-10-01",
    "firm_name": "Example Firm LLP",
    "founded_year": 1987,
    "attorney_count": 46,
    "partner_count": 17,
    "offices": [
        {"city": "Alder Bay", "county": "Larkspur County"},
        {"city": "Stonemill", "county": "Hadley County"},
        {"city": "Port Verity", "county": "Corrin County"},
    ],
    "bar_admissions": ["State of Westmark", "State of Ardenia"],
    "public_agency_clients": 85,
    "matter_counts": {"negotiations": 140, "capital_projects": 60},
    "approved_by": "Margit Solberg",
}
# What the firm said about itself in earlier years. Old proposals carry these numbers.
HISTORY = {
    2022: {"attorneys": 38, "offices": ["Alder Bay", "Stonemill", "Greyhaven"], "clients": 60},
    2023: {"attorneys": 41, "offices": ["Alder Bay", "Stonemill", "Greyhaven"], "clients": 66},
    2024: {"attorneys": 43, "offices": ["Alder Bay", "Stonemill", "Port Verity"], "clients": 72},
}

# ------------------------------------------------------------------ past proposals

PROPOSALS = [
    ("P-2022-01", "City of Fennimore Gap", "city", "general_counsel", "2022-03-11", "lost"),
    ("P-2022-02", "Harlan Springs Fire Protection District", "special_district", "general_counsel", "2022-09-02", "won"),
    ("P-2023-01", "Larch Valley Unified School District", "school_district", "labor", "2023-02-17", "won"),
    ("P-2023-02", "Osprey Mesa Sanitary District", "special_district", "general_counsel", "2023-06-30", "lost"),
    ("P-2023-03", "Ironwood Loop Transit District", "transit", "capital_projects", "2023-10-13", "won"),
    ("P-2024-01", "Town of Wrenfield", "city", "general_counsel", "2024-01-26", "won"),
    ("P-2024-02", "Sandpiper Elementary School District", "school_district", "labor", "2024-05-10", "lost"),
    ("P-2024-03", "Kettle Bend Irrigation District", "special_district", "general_counsel", "2024-08-23", "won"),
    ("P-2025-01", "Saltmarsh Regional Transit Authority", "transit", "capital_projects", "2025-02-07", "lost"),
    ("P-2025-02", "City of Cinder Falls", "city", "general_counsel", "2025-04-18", "won"),
    ("P-2025-03", "Thistledown Community College District", "school_district", "labor", "2025-09-05", "won"),
    ("P-2026-01", "Dunmoor Park and Recreation District", "special_district", "general_counsel", "2026-03-20", "pending"),
    ("P-2026-02", "Quarry Hollow Transit District", "transit", "capital_projects", "2026-06-12", "won"),
]
APPROVER = {"general_counsel": "Margit Solberg", "labor": "Priya Raghunathan",
            "capital_projects": "Tomasz Wieczorek"}

GOVERNING = {"city": "City Council", "special_district": "Board of Directors",
             "school_district": "Board of Trustees", "transit": "Board of Directors"}
CHIEF = {"city": "City Manager", "special_district": "General Manager",
         "school_district": "Superintendent", "transit": "Executive Director"}


def short_of(name):
    if name.startswith("City of"):
        return "the City"
    if name.startswith("Town of"):
        return "the Town"
    return "the " + name.split()[-1]


PRACTICE_SENTENCE = {
    ("general_counsel", "city"): "Our general counsel group serves as city attorney or general counsel and advises on open meetings, public records, land use, contracts and personnel.",
    ("general_counsel", "special_district"): "Our special district group serves as general counsel to water, fire, sanitary and recreation districts and advises on board governance, rates and charges, public works contracts and personnel.",
    ("labor", "school_district"): "Our labor group negotiates collective bargaining agreements for school districts and other public employers and advises on impasse, factfinding and grievances.",
    ("capital_projects", "transit"): "Our capital projects group advises transit agencies and other public owners on design-build procurement, construction contract administration, claims and right-of-way acquisition.",
}
ROLE = {"general_counsel": "city attorney or general counsel", "labor": "chief negotiator",
        "capital_projects": "lead counsel on public capital projects"}
PRACTICE_EXP = {
    ("general_counsel", "city"): "Our general counsel work includes meeting attendance, contract review, public records responses, land use advice and advice on conflicts of interest.",
    ("general_counsel", "special_district"): "Our special district work includes board governance, rates and charges, water supply contracts and public works bidding.",
    ("labor", "school_district"): "Our negotiations work includes successor agreements, reopeners, impasse mediation and factfinding for school and community college districts.",
    ("capital_projects", "transit"): "Our capital project work includes design-build procurement, change order and claims review, and right-of-way acquisition for rail and bus facilities.",
}

T = {}
T["firm_overview"] = [
    "Example Firm LLP is a law firm that represents public agencies. The firm was founded in {FIRM_FOUNDED} and has {FIRM_ATTORNEYS} attorneys in {FIRM_OFFICE_COUNT} offices: {FIRM_OFFICES}. Most of our work is for cities, special districts, school districts and transit agencies. {PRACTICE} We do not represent private parties against the public agencies we serve.",
    "Example Firm LLP has advised public agencies since {FIRM_FOUNDED}. The firm has {FIRM_ATTORNEYS} attorneys and offices in {FIRM_OFFICES}. We currently represent {FIRM_CLIENTS} public agencies as general or special counsel. {PRACTICE} The firm is owned by its partners and has no outside investors.",
    "Example Firm LLP is a public agency law firm with {FIRM_ATTORNEYS} attorneys. Our offices are in {FIRM_OFFICES}. {PRACTICE} Every client has one responsible partner, and that partner stays on the engagement.",
]
T["approach", "general_counsel"] = [
    "We propose to serve {AGENCY} with one lead attorney who attends every regular {GOVERNING_BODY} meeting and one backup attorney who knows the open files. Staff questions that do not need research are answered the same business day. Contracts and resolutions are reviewed within three business days unless staff asks for a faster turn. Before each meeting we review the agenda with the {CHIEF_EXEC} and flag open meeting, public records and conflict of interest questions. A monthly report lists open matters, hours and spending against the retainer.",
    "Day-to-day service to {AGENCY_SHORT} runs through the lead attorney. The lead attorney holds office hours at {AGENCY_SHORT}'s offices twice a month and is available by telephone and email at other times. Urgent requests get a response within two hours during the business day. We keep a shared list of open requests so that staff can see who is handling each one and when it is due. Once a year we give the {GOVERNING_BODY} and staff training on open meeting and conflict of interest rules at no charge.",
]
APPROACH_EXTRA = {
    "city": " For a city we also attend Planning Commission meetings on request and advise on land use and code enforcement.",
    "special_district": " For a district that sets its own rates we also review rate studies and notices for rates and charges, and we advise on water supply contracts and public works bidding as they arise.",
}
T["approach", "labor"] = [
    "We start by reading the current agreements, recent tentative agreements and any open grievances. We then meet the {CHIEF_EXEC} and the business office to cost each likely proposal, and we ask the {GOVERNING_BODY} for bargaining parameters in closed session before the first session. At the table one attorney speaks for {AGENCY_SHORT} and keeps the written record of proposals and counterproposals. After each session we send a short report to the {GOVERNING_BODY}. If the parties reach impasse we prepare the mediation and factfinding presentations ourselves, using the same costing model.",
    "Our approach to negotiations has four parts: preparation, costing, communication and closing. In preparation we compare {AGENCY_SHORT}'s agreements with those of similar employers. In costing we build a model with the business office so that every proposal has a total cost before it is passed across the table. We agree ground rules on communicating with employees at the first session and we draft updates for {AGENCY_SHORT} to send. At closing we draft the tentative agreement language and check it against the table notes before signature.",
]
T["approach", "capital_projects"] = [
    "We advise the project team from procurement through closeout. For a design-build contract we review the request for proposals, the general conditions and the allocation of risk for differing site conditions and utilities. During construction we review every change order request above the delegated threshold and keep a claims log with notice dates. We meet the project manager monthly to review the risk register. For right-of-way acquisition we work to the project schedule and track each parcel from appraisal to possession.",
    "Claims avoidance starts with the contract. We make sure that notice, documentation and dispute resolution steps are clear and that staff are trained to follow them. When a change order request arrives we check entitlement first and price second, and we give the project manager a written recommendation. We prepare {AGENCY_SHORT} for the dispute resolution process under the design-build contract by keeping the project record in order from the first day. On real property we coordinate appraisals, offers and easements with the engineering schedule.",
]
T["team"] = [
    "The team for {AGENCY} is led by a partner who has served as {ROLE} for other public agencies. A second partner is the designated backup and attends meetings when the lead attorney cannot. Associates handle research, contract review and public records responses under the lead attorney's supervision. We do not change the lead attorney without {AGENCY_SHORT}'s consent. The attorneys proposed are listed below.",
    "We staff each engagement with a small team so that {AGENCY_SHORT} always speaks to someone who knows its matters. The lead attorney is responsible for all advice and attends meetings in person. The backup attorney is copied on open matters and can step in on short notice. Work is assigned to the attorney with the right experience at the lowest suitable rate. The attorneys proposed are listed below.",
]
T["experience"] = [
    "Example Firm LLP serves public agencies as {ROLE}. The engagements listed below are the most similar to the work described in the request for proposals. In each one, attorneys proposed for {AGENCY} did the work described. {PRACTICE_EXP}",
    "We have chosen engagements that match {AGENCY_SHORT}'s needs in size and subject matter. {PRACTICE_EXP} We name a client only with the client's consent, so some engagements are described without the client's name.",
]
T["references"] = [
    "References are listed below. Each contact has agreed to speak with {AGENCY_SHORT} about our work.",
    "The clients listed below have worked with the attorneys proposed for {AGENCY}. We have confirmed that each contact is willing to be called.",
]
T["conflicts"] = [
    "We have checked our conflicts records for {AGENCY}, its officials and the parties named in the request for proposals. We found no current or former client whose interests conflict with {AGENCY_SHORT}'s. If a conflict arises during the engagement we will tell {AGENCY_SHORT} in writing at once.",
    "Our conflicts check for {AGENCY} is complete. One former client has a matter that is unrelated to {AGENCY_SHORT} and is described in the attached disclosure. We do not believe it is a conflict, and we will follow {AGENCY_SHORT}'s direction on it.",
]
T["rates"] = [
    "We propose a monthly retainer for general services and hourly rates for special projects and litigation. Rates are fixed for the first two years of the agreement. We do not charge for travel time to regular meetings.",
    "We propose hourly rates with a not-to-exceed amount agreed in advance for each phase of the work. Invoices show the attorney, the task and the time for every entry. We do not bill for internal conferences between attorneys.",
]
T["diversity_local"] = [
    "Example Firm LLP has offices in {FIRM_OFFICES}. The attorneys proposed for {AGENCY} live and work in the region. The firm recruits from law schools in the region and reports the make-up of its attorneys and staff to its partners each year.",
    "Our {OFFICE} office is the closest to {AGENCY_SHORT} and will be the base for this engagement. We buy services such as court reporting and document management from small local businesses where we can. The firm has a written equal opportunity policy, and a hiring committee reviews outcomes each year.",
]
T["transition"] = [
    "We have taken over general counsel and special counsel work from prior counsel many times. In the first thirty days we meet prior counsel, collect open files and calendar every deadline. We meet the {CHIEF_EXEC} and each department head to learn what is pending. We give the {GOVERNING_BODY} a written list of open matters with a recommended next step for each. We do not charge for time spent learning {AGENCY_SHORT}'s files during the transition.",
    "A transition has three steps: files, people and deadlines. We ask prior counsel for a status memo on each open matter and for the complete files. We introduce the team to staff and agree how requests will be sent and tracked. We confirm every litigation and contract deadline against the source documents. For continuity, the same lead attorney and backup attorney stay on the engagement for its full term.",
]
QUESTION = {
    "firm_overview": ["Describe the firm, its history, size and office locations.", "Provide a firm profile including the number of attorneys and offices."],
    "approach": ["Describe the firm's approach to providing the services, including availability and response times.", "Describe your work plan and how you will keep the governing body informed."],
    "team": ["Identify the lead attorney and other proposed team members and their roles.", "Describe the personnel who will be assigned and how the engagement will be staffed."],
    "experience": ["Describe the firm's experience with similar public agency engagements.", "Describe relevant experience in the last five years."],
    "references": ["Provide references from public agency clients.", "List client references with contact information."],
    "conflicts": ["Disclose any actual or potential conflicts of interest.", "Identify any client whose interests may conflict."],
    "rates": ["State proposed fees, hourly rates and any retainer.", "Provide a cost proposal."],
    "diversity_local": ["Describe the firm's local presence and its diversity and small business practices.", "Describe local office and participation by small or local firms."],
    "transition": ["Describe how the firm would take over from current counsel.", "Provide a transition plan and describe staffing continuity."],
}
QTYPES = ["firm_overview", "approach", "team", "experience", "references", "conflicts", "rates",
          "diversity_local", "transition"]

WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def join_list(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def add_months(date, months):
    y, m = divmod(date.month - 1 + months, 12)
    return dt.date(date.year + y, m + 1, min(date.day, 28))


def build_answers(rng):
    answers = []
    n = 0
    for pid, agency, atype, practice, submitted, outcome in PROPOSALS:
        sub = dt.date.fromisoformat(submitted)
        year = sub.year
        tag_agency = year >= 2024          # agency placeholders used from 2024
        tag_facts = year >= 2025           # firm fact placeholders used from 2025
        for qi, qtype in enumerate(QTYPES):
            variants = T.get((qtype, practice)) or T[qtype]
            v = (qi + int(pid[-1]) + year) % len(variants)
            text = variants[v]
            if qtype == "approach" and practice == "general_counsel":
                text += APPROACH_EXTRA[atype]
            text = text.replace("{PRACTICE}", PRACTICE_SENTENCE[(practice, atype)])
            text = text.replace("{PRACTICE_EXP}", PRACTICE_EXP[(practice, atype)])
            text = text.replace("{ROLE}", ROLE[practice])
            text = text.replace("{OFFICE}", "Alder Bay" if year >= 2024 else "Greyhaven")
            if not tag_agency:
                text = text.replace("{AGENCY_SHORT}", short_of(agency)).replace("{AGENCY}", agency)
                text = text.replace("{GOVERNING_BODY}", GOVERNING[atype]).replace("{CHIEF_EXEC}", CHIEF[atype])
                text = text[0].upper() + text[1:]
                text = text.replace(". the ", ". The ")
            if not tag_facts:
                h = HISTORY[year]
                text = (text.replace("{FIRM_ATTORNEYS}", str(h["attorneys"]))
                        .replace("{FIRM_FOUNDED}", "1987")
                        .replace("{FIRM_OFFICE_COUNT}", WORDS[len(h["offices"])])
                        .replace("{FIRM_OFFICES}", join_list(h["offices"]))
                        .replace("{FIRM_CLIENTS}", str(h["clients"])))
            n += 1
            review_by = add_months(sub, 36)
            # some answers from older winning proposals were reviewed again in 2026
            if outcome == "won" and year <= 2023 and rng.random() < 0.7:
                review_by = dt.date(2027, rng.randint(3, 9), 15)
            approved = not (outcome == "pending" and qtype in ("approach", "transition", "team")) and rng.random() > 0.06
            answers.append({
                "id": "A-%04d" % n, "proposal_id": pid, "proposal_agency": agency, "agency_type": atype,
                "practice": practice, "submitted": submitted, "outcome": outcome, "question_type": qtype,
                "question_text": QUESTION[qtype][(qi + year) % 2], "answer_text": text,
                "approved": approved, "approver": APPROVER[practice] if approved else "",
                "review_by": review_by.isoformat(), "tags": [],
            })
    by = {(a["proposal_id"], a["question_type"]): a for a in answers}

    # Deliberate defects. These are the kinds of thing the fact guard exists to catch.
    a = by[("P-2025-02", "approach")]
    a["answer_text"] = a["answer_text"].replace(
        "every regular {GOVERNING_BODY} meeting", "every regular meeting of Cinder Falls' City Council")
    a["tags"].append("defect: source agency name left in")
    a = by[("P-2026-02", "experience")]
    a["answer_text"] += " Our work for QHTD on its maintenance facility is the closest match."
    a["tags"].append("defect: source agency abbreviation left in")
    a = by[("P-2025-03", "team")]
    a["answer_text"] = a["answer_text"].replace(
        "The attorneys proposed are listed below.",
        "Corwin Halloway will serve as chief negotiator. The attorneys proposed are listed below.")
    a["tags"].append("defect: names an attorney who has left the firm")
    a = by[("P-2026-01", "diversity_local")]
    a["answer_text"] = a["answer_text"].replace("Our Alder Bay office", "Our Greyhaven office")
    a["tags"].append("defect: names an office the firm no longer has")
    a = by[("P-2025-01", "approach")]
    a["answer_text"] = a["answer_text"].replace("{AGENCY_SHORT}", "the Authority")
    a["tags"].append("defect: agency short name typed in, not tagged")
    a = by[("P-2025-01", "firm_overview")]
    a["answer_text"] = a["answer_text"].replace("{FIRM_ATTORNEYS}", "44")
    a["tags"].append("defect: head count typed in, not tagged")

    # Three extra answers on water topics from the irrigation district proposal.
    extra = [
        ("Describe how the firm advises on water rates and charges.",
         "When {AGENCY_SHORT} considers new rates and charges we review the rate study with the consultant before it goes to the {GOVERNING_BODY}. We check that the notice, the hearing and the protest count follow the procedure {AGENCY_SHORT} has adopted. We attend the hearing and advise on the record."),
        ("Describe the firm's experience with water supply contracts and groundwater matters.",
         "We draft and negotiate water supply contracts, transfer agreements and agreements with neighbouring agencies. On groundwater matters we advise the {GOVERNING_BODY} on its role in the local groundwater agency and review that agency's plans and fees."),
        ("Describe how the firm advises on public works contracts and bidding.",
         "We keep a set of public works contract templates for {AGENCY_SHORT} and update them when staff reports a problem. We review bid documents before they are issued and advise on bid protests and bidder responsiveness within one business day."),
    ]
    for q, text in extra:
        n += 1
        answers.append({
            "id": "A-%04d" % n, "proposal_id": "P-2024-03", "proposal_agency": "Kettle Bend Irrigation District",
            "agency_type": "special_district", "practice": "general_counsel", "submitted": "2024-08-23",
            "outcome": "won", "question_type": "approach", "question_text": q, "answer_text": text,
            "approved": True, "approver": APPROVER["general_counsel"], "review_by": "2027-08-23",
            "tags": ["water"],
        })
    return answers


# ------------------------------------------------------------------ attorneys

BIOS = [
    # id, name, title, status, admit_year, office, practices, agency_types, subjects, roles
    ("B01", "Margit Solberg", "Partner", "active", 1996, "Alder Bay", ["general_counsel"], ["city", "special_district"], ["governance", "open meetings", "public records"], ["general counsel", "city attorney"]),
    ("B02", "Desmond Achebe", "Partner", "active", 2004, "Alder Bay", ["general_counsel"], ["city"], ["land use", "open meetings", "public contracting", "code enforcement"], ["city attorney"]),
    ("B03", "Priya Raghunathan", "Partner", "active", 2006, "Stonemill", ["labor"], ["school_district", "city"], ["collective bargaining", "personnel", "schools"], ["chief negotiator"]),
    ("B04", "Tomasz Wieczorek", "Partner", "active", 2001, "Port Verity", ["capital_projects"], ["transit", "special_district"], ["construction", "claims", "public contracting", "transit"], ["special counsel"]),
    ("B05", "Leilani Kahananui", "Partner", "active", 2009, "Stonemill", ["general_counsel"], ["special_district"], ["water", "rates and charges", "governance", "public contracting"], ["general counsel"]),
    ("B06", "Corwin Halloway", "Partner", "departed", 1999, "Stonemill", ["labor"], ["school_district"], ["collective bargaining", "schools"], ["chief negotiator"]),
    ("B07", "Nadia El-Masri", "Partner", "active", 2008, "Alder Bay", ["general_counsel"], ["city"], ["land use", "code enforcement", "real property"], ["city attorney"]),
    ("B08", "Jerome Fitzwilliam", "Of Counsel", "active", 1991, "Port Verity", ["general_counsel"], ["special_district"], ["water", "rates and charges", "real property"], ["general counsel"]),
    ("B09", "Ingrid Castellane", "Partner", "active", 2010, "Stonemill", ["labor"], ["school_district"], ["collective bargaining", "schools", "personnel"], ["chief negotiator"]),
    ("B10", "Rafael Montoya-Reyes", "Senior Associate", "active", 2015, "Alder Bay", ["general_counsel"], ["city", "special_district"], ["public records", "open meetings", "public contracting"], ["assistant general counsel"]),
    ("B11", "Hyejin Baek", "Senior Associate", "active", 2016, "Stonemill", ["labor"], ["school_district"], ["collective bargaining", "personnel"], ["negotiations support"]),
    ("B12", "Oluwaseun Adeyemi", "Senior Associate", "active", 2014, "Port Verity", ["capital_projects"], ["transit"], ["construction", "claims", "public contracting"], ["project counsel"]),
    ("B13", "Bridget O'Callaghan", "Associate", "active", 2019, "Alder Bay", ["general_counsel"], ["city"], ["public records", "code enforcement"], ["associate"]),
    ("B14", "Mateus Carvalho", "Associate", "active", 2020, "Stonemill", ["labor"], ["school_district", "city"], ["personnel", "collective bargaining"], ["associate"]),
    ("B15", "Anneliese Brandt", "Associate", "active", 2018, "Stonemill", ["general_counsel"], ["special_district"], ["water", "public contracting", "governance"], ["associate"]),
    ("B16", "Darius Farrokhzad", "Senior Associate", "active", 2013, "Port Verity", ["capital_projects"], ["transit", "city"], ["real property", "construction", "transit"], ["right-of-way counsel"]),
    ("B17", "Simone Beauregard", "Partner", "active", 2005, "Port Verity", ["capital_projects"], ["transit"], ["transit", "construction", "real property", "claims"], ["special counsel"]),
    ("B18", "Kwabena Osei", "Associate", "active", 2021, "Alder Bay", ["general_counsel"], ["city", "special_district"], ["open meetings", "public contracting"], ["associate"]),
    ("B19", "Talia Rosenthal", "Senior Associate", "active", 2012, "Stonemill", ["labor"], ["school_district"], ["schools", "personnel", "collective bargaining"], ["negotiations support"]),
    ("B20", "Viktor Lindahl", "Of Counsel", "active", 1994, "Port Verity", ["capital_projects"], ["transit", "special_district"], ["claims", "construction"], ["claims counsel"]),
    ("B21", "Marisela Quintanar", "Associate", "active", 2022, "Alder Bay", ["general_counsel"], ["city"], ["public records"], ["associate"]),
    ("B22", "Gideon Abramowitz", "Partner", "active", 2002, "Stonemill", ["general_counsel"], ["special_district", "city"], ["governance", "rates and charges", "personnel"], ["general counsel"]),
    ("B23", "Chiara Benedetti", "Associate", "active", 2023, "Stonemill", ["labor"], ["school_district"], ["collective bargaining"], ["associate"]),
    ("B24", "Emeka Nwosu", "Senior Associate", "active", 2011, "Stonemill", ["general_counsel"], ["special_district"], ["water", "real property", "rates and charges"], ["assistant general counsel"]),
    ("B25", "Fiona MacAllister", "Associate", "active", 2019, "Port Verity", ["capital_projects"], ["transit"], ["construction", "public contracting"], ["associate"]),
]
AGENCY_WORD = {"city": "cities", "special_district": "special districts", "school_district": "school districts",
               "transit": "transit agencies"}


def build_bios():
    out = []
    for bid, name, title, status, admit, office, practices, atypes, subjects, roles in BIOS:
        text = "%s advises %s on %s." % (name.split()[0], join_list([AGENCY_WORD[a] for a in atypes]),
                                         join_list(subjects))
        out.append({"id": bid, "name": name, "title": title, "status": status, "admit_year": admit,
                    "office": office, "practices": practices, "agency_types": atypes, "subjects": subjects,
                    "roles": roles, "bio_text": text,
                    "departed_date": "2025-08-31" if status == "departed" else ""})
    return out


# ------------------------------------------------------------------ experience

PLACES = ["Harlan Springs", "Osprey Mesa", "Kettle Bend", "Dunmoor", "Larch Valley", "Sandpiper",
          "Thistledown", "Ironwood Loop", "Saltmarsh", "Fennimore Gap", "Cinder Falls", "Wrenfield",
          "Quarry Hollow", "Brindle Creek", "Mossgate", "Tallowfield", "Vesper Point", "Ashmantle",
          "Juniper Landing", "Corbel Heights", "Lantern Rock", "Pellam Marsh", "Sorrel Canyon",
          "Halewick", "Bramblewood", "Emberlow", "Nettlefield", "Oxbow Terrace", "Candlewick",
          "Fogbank"]
REGIONS = ["the Central Valley", "the north coast", "the foothills", "the inland valleys", "the south coast"]
SD_KINDS = ["Water", "Fire Protection", "Sanitary", "Irrigation", "Park and Recreation",
            "Community Services", "Harbor"]
SCHOOL_KINDS = ["Unified School", "Elementary School", "Community College"]
EXP_PLAN = [  # (agency_type, practice, count, subjects pool, role)
    ("city", "general_counsel", 14, ["land use", "open meetings", "public records", "public contracting", "code enforcement", "personnel", "governance"], "city attorney"),
    ("special_district", "general_counsel", 18, ["water", "rates and charges", "governance", "public contracting", "open meetings", "public records", "personnel", "real property"], "general counsel"),
    ("school_district", "labor", 14, ["collective bargaining", "schools", "personnel"], "chief negotiator"),
    ("transit", "capital_projects", 10, ["construction", "claims", "real property", "transit", "public contracting"], "special counsel"),
    ("city", "labor", 2, ["collective bargaining", "personnel"], "chief negotiator"),
    ("special_district", "capital_projects", 2, ["construction", "claims", "public contracting"], "special counsel"),
]
LEADS = {("city", "general_counsel"): ["B02", "B07", "B01"], ("special_district", "general_counsel"): ["B05", "B22", "B08"],
         ("school_district", "labor"): ["B03", "B09", "B06"], ("transit", "capital_projects"): ["B04", "B17"],
         ("city", "labor"): ["B03"], ("special_district", "capital_projects"): ["B04", "B20"]}
SUMMARY = {
    "general_counsel": "Served as %s. Advised the governing body and staff on %s.",
    "labor": "Served as %s in successor negotiations. Work included %s.",
    "capital_projects": "Served as %s on a public capital project. Work included %s.",
}


def build_experience(rng):
    used = {p[1] for p in PROPOSALS}
    out = []
    n = 0
    for atype, practice, count, pool, role in EXP_PLAN:
        for _ in range(count):
            for _try in range(200):
                place = rng.choice(PLACES)
                if atype == "city":
                    kind = ""
                    name = ("City of %s" if rng.random() < 0.8 else "Town of %s") % place
                elif atype == "special_district":
                    kind = rng.choice(SD_KINDS)
                    name = "%s %s District" % (place, kind)
                elif atype == "school_district":
                    kind = rng.choice(SCHOOL_KINDS)
                    name = "%s %s District" % (place, kind)
                else:
                    kind = ""
                    name = "%s %s" % (place, rng.choice(["Transit District", "Regional Transit Authority"]))
                if name not in used:
                    used.add(name)
                    break
            n += 1
            subjects = sorted(rng.sample(pool, min(len(pool), rng.randint(2, 4))))
            if atype == "special_district" and kind in ("Water", "Irrigation") and "water" not in subjects:
                subjects = sorted(subjects + ["water"])
            start = rng.randint(2012, 2024)
            ongoing = rng.random() < 0.45
            end = None if ongoing else min(2026, start + rng.randint(1, 8))
            consent = rng.random() < 0.55
            region = rng.choice(REGIONS)
            if atype == "city":
                anon = "a city of about %d,000 residents in %s" % (rng.randint(2, 18) * 5, region)
            elif atype == "special_district":
                anon = "a %s district in %s" % (kind.lower(), region)
            elif atype == "school_district":
                anon = "a %s district with about %d,000 students" % (kind.lower(), rng.randint(3, 30))
            else:
                anon = "a regional transit agency in %s" % region
            if not consent and rng.random() < 0.25:
                anon = ""   # no approved description: the record cannot be printed at all
            out.append({
                "id": "E-%03d" % n, "client_name": name, "client_consent": consent,
                "anonymized_description": anon, "agency_type": atype, "practice": practice,
                "subjects": subjects, "role": role, "start_year": start, "end_year": end,
                "summary": SUMMARY[practice] % (role, join_list(subjects)),
                "lead_attorney_id": rng.choice(LEADS[(atype, practice)]),
            })
    return out


# ------------------------------------------------------------------ references

FIRST = ["Alma", "Benedikt", "Carys", "Dov", "Eirlys", "Fabrizio", "Gwendolyn", "Hamza", "Isolde", "Joaquim",
         "Katarzyna", "Lorcan", "Mirabel", "Nikolai", "Oriana", "Percival", "Quenby", "Rosalind", "Stellan",
         "Thandiwe", "Ulrike", "Valentin", "Winifred", "Xiomara", "Yusuf", "Zelda"]
LAST = ["Arkwright", "Bellamy", "Cathcart", "Drummond", "Eastlake", "Fairweather", "Garrity", "Holloway-Reed",
        "Ingleby", "Jessup", "Kilbride", "Lockhart", "Mayhew", "Northcott", "Ormsby", "Pemberton", "Quarles",
        "Ravenscroft", "Stanhope", "Trevelyan", "Underhill", "Vance", "Whitcombe", "Yarrow"]
REF_TITLE = {"city": "City Manager", "special_district": "General Manager",
             "school_district": "Assistant Superintendent", "transit": "Chief Capital Officer"}


def build_references(rng, experience):
    out = []
    names = set()
    n = 0
    for e in experience:
        if rng.random() > 0.5:
            continue
        while True:
            contact = "%s %s" % (rng.choice(FIRST), rng.choice(LAST))
            if contact not in names:
                names.add(contact)
                break
        n += 1
        consent = e["client_consent"] and rng.random() < 0.85
        month = rng.randint(1, 22)
        confirmed = dt.date(2025 + (month - 1) // 12, (month - 1) % 12 + 1, 10)
        local = contact.lower().replace(" ", ".").replace("'", "")
        out.append({
            "id": "REF-%03d" % n, "experience_id": e["id"], "client_name": e["client_name"],
            "contact_name": contact, "contact_title": REF_TITLE[e["agency_type"]],
            "phone": "555-01%02d" % n, "email": "%s@%s.example" % (local, e["client_name"].lower().replace(" ", "")[:18]),
            "client_consent": consent, "last_confirmed": confirmed.isoformat(),
            "agency_type": e["agency_type"], "practice": e["practice"],
        })
    return out


# ------------------------------------------------------------------ other library files

RATE_SCHEDULES = [
    {"id": "RS-2025", "name": "Public agency rate schedule 2025", "effective": "2025-01-01", "expires": "2025-12-31",
     "approved_by": "Margit Solberg",
     "rates": [{"title": "Partner", "hourly": 395}, {"title": "Of Counsel", "hourly": 375},
               {"title": "Senior Associate", "hourly": 335}, {"title": "Associate", "hourly": 295}]},
    {"id": "RS-2026", "name": "Public agency rate schedule 2026", "effective": "2026-01-01", "expires": "2026-12-31",
     "approved_by": "Margit Solberg",
     "rates": [{"title": "Partner", "hourly": 410}, {"title": "Of Counsel", "hourly": 390},
               {"title": "Senior Associate", "hourly": 350}, {"title": "Associate", "hourly": 305}]},
    {"id": "RS-2027", "name": "Public agency rate schedule 2027", "effective": "2027-01-01", "expires": "2027-12-31",
     "approved_by": "",
     "rates": [{"title": "Partner", "hourly": 425}, {"title": "Of Counsel", "hourly": 405},
               {"title": "Senior Associate", "hourly": 365}, {"title": "Associate", "hourly": 315}]},
]
STANDARD_FORMS = [
    {"id": "SF-01", "name": "Non-Collusion Declaration", "aliases": ["Non-Collusion Affidavit", "Noncollusion Declaration"],
     "file": "forms/non_collusion.docx", "requires_signature": True, "requires_notary": False, "last_reviewed": "2026-02-10"},
    {"id": "SF-02", "name": "Proposer Information Sheet", "aliases": ["Proposer Information Form", "Firm Information Sheet"],
     "file": "forms/proposer_information.docx", "requires_signature": False, "requires_notary": False, "last_reviewed": "2026-02-10"},
    {"id": "SF-03", "name": "Proposer Certification", "aliases": ["Proposal Certification", "Proposal Signature Page", "Signed Proposal Certification"],
     "file": "forms/proposer_certification.docx", "requires_signature": True, "requires_notary": False, "last_reviewed": "2026-02-10"},
    {"id": "SF-04", "name": "Insurance Acknowledgment", "aliases": ["Insurance Certification", "Statement of Insurance", "Certificate of Insurance"],
     "file": "forms/insurance_acknowledgment.docx", "requires_signature": True, "requires_notary": False, "last_reviewed": "2025-06-30"},
    {"id": "SF-05", "name": "Addendum Acknowledgment", "aliases": ["Acknowledgment of Addenda"],
     "file": "forms/addendum_acknowledgment.docx", "requires_signature": True, "requires_notary": False, "last_reviewed": "2026-02-10"},
    {"id": "SF-06", "name": "Conflict of Interest Disclosure", "aliases": ["Conflict of Interest Disclosure Form"],
     "file": "forms/conflict_disclosure.docx", "requires_signature": True, "requires_notary": False, "last_reviewed": "2026-02-10"},
]
WORKPLAN = {
    "note": "Owners and lead times used to build the compliance matrix. Lead time is business days before the submission deadline.",
    "owners": {
        "cover_letter": "Responsible partner", "firm_overview": "Proposal lead", "approach": "Practice lead",
        "team": "Practice lead", "experience": "Proposal coordinator", "references": "Responsible partner",
        "conflicts": "Conflicts team", "rates": "Pricing partner", "diversity_local": "Proposal lead",
        "transition": "Practice lead", "disclosure": "General counsel of the firm", "other": "Proposal lead",
        "form": "Proposal coordinator", "min_qual": "Practice lead", "insurance": "Risk manager",
        "submission": "Proposal coordinator", "addendum": "Proposal lead",
    },
    "lead_days": {
        "conflicts": 10, "references": 7, "content": 6, "min_qual": 6, "rates": 4, "disclosure": 4,
        "insurance": 4, "form": 3, "cover_letter": 2, "addendum": 2, "submission": 1,
    },
    "words_per_page": 450,
    "review_months_after_harvest": 18,
    "reference_reconfirm_days": 365,
    "firm_facts_max_age_days": 180,
}
MAPPING = {
    "note": "Maps the firm's own files and column names onto the canonical schemas in desk/schemas.py. "
            "Here the demo files already use canonical names, so only file names are given.",
    "past_answers": {"file": "past_answers.json"},
    "experience": {"file": "experience.json"},
    "bios": {"file": "bios.json"},
    "rate_schedules": {"file": "rate_schedules.json"},
    "references": {"file": "references.json"},
    "standard_forms": {"file": "standard_forms.json"},
    "firm_facts": {"file": "firm_facts.json"},
    "workplan": {"file": "workplan.json"},
}


def dump(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


def main():
    rng = random.Random(SEED)
    os.makedirs(OUT, exist_ok=True)
    answers = build_answers(rng)
    bios = build_bios()
    experience = build_experience(rng)
    references = build_references(rng, experience)
    facts = dict(FIRM_FACTS)
    facts["departed_attorneys"] = [b["name"] for b in bios if b["status"] == "departed"]
    dump("past_answers.json", answers)
    dump("bios.json", bios)
    dump("experience.json", experience)
    dump("references.json", references)
    dump("rate_schedules.json", RATE_SCHEDULES)
    dump("standard_forms.json", STANDARD_FORMS)
    dump("firm_facts.json", facts)
    dump("workplan.json", WORKPLAN)
    dump("mapping.json", MAPPING)
    print("answers %d, proposals %d, experience %d, bios %d, references %d" % (
        len(answers), len(PROPOSALS), len(experience), len(bios), len(references)))


if __name__ == "__main__":
    main()
