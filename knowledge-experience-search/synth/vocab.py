"""Vocabulary for the synthetic corpus. Everything here is invented.

Topic terms are ordinary drafting vocabulary used as search fodder. No
sentence built from them states what any law requires.
"""

OFFICES = ["Caldmoor", "Port Wenrick", "Estermere", "Aldhaven", "Tavish Falls",
           "Brannock", "Marlowe Heights", "Senna Bay"]
NEW_OFFICES = ["Tavish Falls", "Marlowe Heights", "Senna Bay"]

FORUMS = ["State of Caldmoor", "State of Wenrick", "Estermere County Superior Court",
          "Northern District of Caldmoor", "Brannock Court of Chancery", "City of Aldhaven",
          "Tavish County", "Province of Sennamar", "Marlowe Planning Commission",
          "Wenrick Court of Appeal", "City of Estermere", "Aldhaven Tax Tribunal"]

INDUSTRIES = ["logistics", "food and beverage", "software", "life sciences", "property",
              "energy", "hospitality", "manufacturing", "financial services", "public sector",
              "healthcare", "retail"]

CLIENT_STEMS = ["Quellmar", "Vostrand", "Thessaby", "Orrinwick", "Zemblay", "Kaldrith",
                "Pellamoor", "Ulvenholt", "Brimsark", "Dovrane", "Ystwell", "Cothelby",
                "Fenwrath", "Grindelow", "Jossamer", "Luthmoor", "Mirrowby", "Skellane",
                "Narrowmere", "Tolvaddon", "Wexcombe", "Harrowick", "Ebbfleeting", "Calloway Fen",
                "Ostrander Vale", "Pyrewick", "Rathmullen", "Sorrelby", "Umberleigh Cross",
                "Varnholt", "Quenby Rise", "Lindqvale", "Marrowgate", "Ashquill", "Brackenmoor",
                "Dunhallow", "Eskerfield", "Feldspar Row", "Glimmerton", "Hollinsby"]
CLIENT_SUFFIXES = ["Group", "Holdings", "Partners", "Works", "Trust", "Cooperative",
                   "Industries", "Ventures"]

FIRST_NAMES = ["Amara", "Bastien", "Calla", "Dmitri", "Eleni", "Farid", "Greta", "Hollis",
               "Imani", "Joaquin", "Keiko", "Lorcan", "Mirela", "Nikhil", "Odette", "Piotr",
               "Quinn", "Rosalind", "Soren", "Tamsin", "Ugo", "Valentina", "Wendell", "Xiomara",
               "Yusuf", "Zelda", "Anselm", "Brigid", "Cormac", "Dalia"]
SURNAMES = ["Ashcombe", "Varrowby", "Tindlewick", "Okonmere", "Halvorsby", "Quistrel",
            "Dellamoor", "Pennwarden", "Strathmoor", "Ibekwell", "Castellane", "Wrenfold",
            "Marchetto", "Nakashiro", "Oyelaranmi", "Brandvold", "Fenniscourt", "Guillaumet",
            "Hadjipetrou", "Jorvikson", "Kowalczynsk", "Lindenmeyr", "Mbekiwa", "Novakovitch",
            "Ostergaarde", "Pradhanam", "Rasmundsen", "Szymborsk", "Thorvaldsby", "Underhaye",
            "Vasquelin", "Whitlocke", "Yamadera", "Zielinskov", "Abernathey", "Bexleyford",
            "Corriveaux", "Drummondale", "Ellingsworth", "Fairweatherby"]

CODENAMES = ["Halcyon", "Cinderford", "Tamarisk", "Orrery", "Quillon", "Vesper", "Lodestar",
             "Kestrel", "Juniper", "Saffron", "Tundra", "Cobalt", "Larkspur", "Onyx", "Sextant",
             "Marram", "Galleon", "Wicklow"]

DOC_LABELS = {"brief": "Brief", "motion": "Motion", "agreement": "Agreement", "memo": "Memo",
              "staff report": "Staff report", "opinion letter": "Opinion letter",
              "checklist": "Checklist", "form": "Form"}
DOC_CODES = {"brief": "BRF", "motion": "MOT", "agreement": "AGR", "memo": "MEM",
             "staff report": "RPT", "opinion letter": "OPN", "checklist": "CHK", "form": "FRM"}

# practice key -> name, matter types (most to least common), doc type weights, topics
PRACTICES = {
    "corp": {
        "name": "Corporate and M&A",
        "matter_types": ["asset purchase", "stock purchase", "merger", "minority investment", "joint venture"],
        "doc_types": {"agreement": 4, "memo": 3, "checklist": 2, "form": 1, "opinion letter": 1},
        "topics": {
            "earn-out provisions": ["earn-out", "milestone payment", "revenue target", "acceleration event", "earn-out period", "buyer covenant", "set-off right", "accounting principles"],
            "indemnification cap and basket": ["indemnification cap", "deductible basket", "tipping basket", "survival period", "fundamental representations", "escrow holdback", "materiality scrape", "losses definition"],
            "working capital adjustment": ["working capital adjustment", "closing statement", "target net working capital", "dispute notice", "independent accountant", "estimated closing balance", "true-up payment", "collar"],
            "material adverse effect": ["material adverse effect", "carve-out", "disproportionate impact", "bring-down condition", "termination right", "interim period", "ordinary course covenant"],
            "disclosure schedules": ["disclosure schedule", "schedule update", "knowledge qualifier", "data room", "specific disclosure", "general disclosure", "cross-reference"],
            "transition services": ["transition services agreement", "service level", "cost-plus fee", "service term", "exit plan", "shared systems", "migration support"],
            "drag-along and tag-along rights": ["drag-along right", "tag-along right", "right of first refusal", "preemptive right", "transfer restriction", "permitted transferee", "shareholder agreement"],
            "closing deliverables": ["closing checklist", "officer certificate", "good standing certificate", "bring-down certificate", "funds flow memorandum", "signature pages", "release of liens"],
        },
    },
    "lit": {
        "name": "Commercial litigation",
        "matter_types": ["contract dispute", "business tort", "shareholder dispute", "injunction proceeding", "class action defense"],
        "doc_types": {"motion": 4, "brief": 3, "memo": 2, "checklist": 1},
        "topics": {
            "forum selection clause": ["forum selection clause", "improper venue", "transfer of venue", "mandatory clause", "permissive clause", "convenience of parties", "enforceability"],
            "personal jurisdiction": ["personal jurisdiction", "minimum contacts", "purposeful availment", "jurisdictional discovery", "general jurisdiction", "specific jurisdiction", "forum contacts"],
            "preliminary injunction": ["preliminary injunction", "irreparable harm", "balance of hardships", "status quo", "injunction bond", "temporary restraining order", "expedited hearing"],
            "summary judgment": ["summary judgment", "undisputed facts", "statement of facts", "genuine dispute", "record evidence", "supporting declaration", "cross-motion"],
            "discovery sanctions": ["discovery sanctions", "spoliation", "litigation hold", "motion to compel", "privilege log", "meet and confer", "protective order"],
            "expert exclusion": ["expert exclusion", "expert report", "methodology challenge", "damages model", "rebuttal expert", "expert deposition", "reliability"],
            "class certification": ["class certification", "commonality", "predominance", "class representative", "numerosity", "class definition", "opt-out notice"],
            "arbitration clause enforcement": ["motion to compel arbitration", "arbitration clause", "delegation provision", "waiver of arbitration", "stay of proceedings", "arbitral seat", "unconscionability"],
        },
    },
    "re": {
        "name": "Real estate",
        "matter_types": ["commercial lease", "purchase and sale", "construction", "property financing", "ground lease"],
        "doc_types": {"agreement": 4, "memo": 2, "checklist": 2, "form": 2, "opinion letter": 1},
        "topics": {
            "lease assignment and subletting": ["lease assignment", "sublease consent", "landlord consent", "recapture right", "change of control", "assignee covenant", "guaranty release"],
            "tenant improvement allowance": ["tenant improvement allowance", "work letter", "punch list", "substantial completion", "construction draw", "landlord work", "rent commencement"],
            "purchase and sale due diligence": ["due diligence period", "title commitment", "survey exception", "estoppel certificate", "earnest money", "environmental assessment", "closing extension"],
            "access easement": ["access easement", "reciprocal easement", "maintenance obligation", "easement relocation", "burdened parcel", "benefited parcel", "utility corridor"],
            "operating expense passthrough": ["operating expenses", "common area maintenance", "expense cap", "audit right", "gross-up", "base year", "reconciliation statement"],
            "ground lease financing": ["ground lease", "leasehold mortgage", "lender cure right", "new lease provision", "rent reset", "fee mortgage subordination", "reversion"],
            "construction contract": ["guaranteed maximum price", "change order", "retainage", "liquidated damages", "completion date", "contractor lien waiver", "schedule of values"],
            "option to purchase": ["purchase option", "right of first offer", "option exercise notice", "appraisal procedure", "option price", "memorandum of option", "option term"],
        },
    },
    "land": {
        "name": "Public agency and land use",
        "matter_types": ["zoning entitlement", "municipal advisory", "environmental review", "public contract", "annexation"],
        "doc_types": {"staff report": 4, "memo": 3, "opinion letter": 2, "agreement": 1, "form": 1},
        "topics": {
            "conditional use permit": ["conditional use permit", "conditions of approval", "planning commission", "findings of approval", "permit revocation", "neighbourhood compatibility", "hours of operation"],
            "zoning variance": ["zoning variance", "hardship finding", "setback encroachment", "height limit", "board of adjustment", "special circumstances", "nonconforming structure"],
            "development agreement": ["development agreement", "vested rights", "public benefit", "phasing schedule", "impact fee credit", "annual review", "term extension"],
            "environmental review": ["environmental review", "mitigation measure", "traffic study", "initial study", "negative declaration", "cumulative impact", "monitoring program"],
            "public bidding": ["competitive bidding", "bid protest", "responsive bid", "lowest responsible bidder", "bid bond", "notice inviting bids", "rejection of bids"],
            "open meeting procedures": ["open meeting", "agenda posting", "closed session", "public comment", "quorum", "serial meeting", "cure and correct"],
            "subdivision map": ["tentative map", "final map", "parcel map", "dedication", "subdivision improvement agreement", "map extension", "lot line adjustment"],
            "short-term rental ordinance": ["short-term rental", "rental registration", "occupancy tax", "nuisance abatement", "permit cap", "host platform", "enforcement citation"],
        },
    },
    "emp": {
        "name": "Employment",
        "matter_types": ["wage claim defense", "executive agreement", "workplace investigation", "restrictive covenant dispute", "reduction in force"],
        "doc_types": {"agreement": 3, "memo": 3, "form": 2, "checklist": 1, "motion": 1, "brief": 1},
        "topics": {
            "non-compete covenant": ["non-compete covenant", "non-solicitation", "garden leave", "protectable interest", "geographic scope", "covenant duration", "blue-pencil"],
            "severance agreement": ["severance agreement", "release of claims", "consideration period", "revocation period", "non-disparagement", "cooperation clause", "benefits continuation"],
            "workplace investigation": ["workplace investigation", "witness interview", "investigation report", "credibility assessment", "retaliation complaint", "interim measures", "investigator notes"],
            "overtime classification": ["overtime classification", "exempt status", "meal period", "timekeeping records", "regular rate", "off-the-clock work", "wage statement"],
            "executive employment agreement": ["executive employment agreement", "good reason", "cause definition", "equity acceleration", "bonus target", "clawback", "change in control"],
            "reduction in force": ["reduction in force", "selection criteria", "adverse impact analysis", "notice period", "separation package", "redeployment", "decisional unit"],
            "reasonable accommodation": ["reasonable accommodation", "interactive process", "medical certification", "essential functions", "leave of absence", "undue hardship", "return to work"],
            "employee arbitration agreement": ["employee arbitration agreement", "class waiver", "opt-out window", "electronic acknowledgment", "rollout notice", "injunctive relief carve-out", "fee allocation"],
        },
    },
    "ip": {
        "name": "Intellectual property",
        "matter_types": ["technology transaction", "trademark prosecution", "trade secret dispute", "patent licensing", "copyright dispute"],
        "doc_types": {"agreement": 3, "memo": 2, "opinion letter": 2, "brief": 1, "motion": 1, "form": 1},
        "topics": {
            "trademark opposition": ["trademark opposition", "likelihood of confusion", "notice of opposition", "priority date", "coexistence agreement", "specimen of use", "descriptiveness"],
            "patent license": ["patent license", "field of use", "royalty rate", "most favoured licensee", "sublicense right", "improvement grant-back", "royalty audit"],
            "trade secret misappropriation": ["trade secret misappropriation", "reasonable measures", "identification of trade secrets", "forensic imaging", "inevitable disclosure", "departing employee", "confidentiality designation"],
            "software license": ["software license agreement", "source code escrow", "licence metrics", "acceptance testing", "maintenance and support", "open source disclosure", "usage audit"],
            "copyright takedown": ["takedown notice", "counter-notice", "repeat infringer", "substantial similarity", "fair use analysis", "licensing history", "registration certificate"],
            "domain name dispute": ["domain name dispute", "bad faith registration", "confusingly similar", "legitimate interest", "transfer order", "panel decision", "registrar lock"],
            "joint development": ["joint development agreement", "background technology", "foreground ownership", "joint ownership", "commercialization right", "publication review", "steering committee"],
            "chain of title review": ["chain of title", "invention assignment", "encumbrance search", "freedom to operate", "intellectual property schedule", "employee inventor", "lien release"],
        },
    },
    "fin": {
        "name": "Banking and finance",
        "matter_types": ["syndicated loan", "asset-based loan", "acquisition finance", "loan workout", "project finance"],
        "doc_types": {"agreement": 4, "opinion letter": 2, "checklist": 2, "memo": 2, "form": 1},
        "topics": {
            "financial covenants": ["financial covenant", "leverage ratio", "fixed charge coverage", "equity cure", "covenant holiday", "compliance certificate", "earnings add-back"],
            "intercreditor arrangements": ["intercreditor agreement", "payment subordination", "standstill period", "lien priority", "turnover provision", "buy-out right", "enforcement action"],
            "security interest perfection": ["security agreement", "financing statement", "perfection certificate", "deposit account control", "collateral description", "after-acquired property", "lien search"],
            "forbearance agreement": ["forbearance agreement", "specified default", "forbearance period", "reservation of rights", "milestone covenant", "default interest", "lender release"],
            "borrowing base": ["borrowing base", "eligible receivables", "advance rate", "field examination", "availability reserve", "concentration limit", "borrowing base certificate"],
            "conditions precedent": ["conditions precedent", "closing opinion", "solvency certificate", "payoff letter", "customer identification", "incumbency certificate", "funding notice"],
            "amendment and waiver": ["amendment and waiver", "required lenders", "consent fee", "amend and extend", "incremental facility", "repricing", "unanimous consent"],
            "guaranty and credit support": ["guaranty", "upstream guaranty", "guarantor release", "limited recourse", "completion guaranty", "non-recourse carve-out", "keepwell"],
        },
    },
    "tax": {
        "name": "Tax",
        "matter_types": ["transaction structuring", "tax controversy", "state and local tax", "partnership tax", "exempt organization"],
        "doc_types": {"memo": 4, "opinion letter": 3, "form": 1, "checklist": 1, "brief": 1},
        "topics": {
            "tax-free reorganization": ["tax-free reorganization", "continuity of interest", "boot", "business purpose", "step transaction", "plan of reorganization", "basis carryover"],
            "partnership allocations": ["partnership allocation", "capital account", "targeted allocation", "distribution waterfall", "tax distribution", "deficit restoration", "profits interest"],
            "sales tax nexus": ["sales tax nexus", "economic nexus", "marketplace facilitator", "voluntary disclosure", "exemption certificate", "sourcing rule", "lookback period"],
            "transfer pricing documentation": ["transfer pricing", "comparability analysis", "arm's length range", "intercompany agreement", "benchmarking study", "cost sharing", "local file"],
            "audit defence": ["information document request", "audit defence", "statute extension", "protest letter", "appeals conference", "closing agreement", "penalty abatement"],
            "tax indemnity": ["tax indemnity", "pre-closing tax period", "straddle period", "tax contest", "refund entitlement", "transfer taxes", "tax return preparation"],
            "unrelated business income": ["unrelated business income", "exempt purpose", "royalty exclusion", "debt-financed property", "private benefit", "intermediate sanctions", "public support test"],
            "cross-border withholding": ["withholding tax", "treaty relief", "beneficial owner", "gross-up clause", "withholding certificate", "permanent establishment", "source of income"],
        },
    },
    "priv": {
        "name": "Privacy and data",
        "matter_types": ["privacy program", "vendor contracting", "breach response", "product counselling", "regulatory inquiry"],
        "doc_types": {"memo": 3, "agreement": 3, "checklist": 2, "form": 2},
        "topics": {
            "data breach notification": ["data breach notification", "incident response plan", "forensic report", "notification letter", "regulator notice", "credit monitoring", "incident timeline"],
            "data processing agreement": ["data processing agreement", "subprocessor", "processing instructions", "security measures", "audit clause", "deletion on termination", "processor liability"],
            "privacy policy update": ["privacy policy", "notice at collection", "categories of personal information", "purpose limitation", "policy changelog", "layered notice", "plain-language summary"],
            "cross-border data transfer": ["cross-border transfer", "transfer impact assessment", "standard contractual clauses", "onward transfer", "data localisation", "transfer register", "supplementary measures"],
            "data subject requests": ["data subject request", "identity verification", "access request", "deletion request", "response deadline", "request log", "authorised agent"],
            "vendor security assessment": ["vendor security assessment", "security questionnaire", "penetration test", "remediation plan", "risk tier", "encryption standard", "access control"],
            "cookie consent": ["cookie consent", "consent banner", "tracking technology", "preference centre", "opt-out signal", "cookie audit", "tag manager"],
            "records retention schedule": ["records retention schedule", "retention period", "legal hold", "disposition", "records inventory", "backup rotation", "archive policy"],
        },
    },
    "te": {
        "name": "Trusts and estates",
        "matter_types": ["estate plan", "trust administration", "probate", "fiduciary dispute", "charitable planning"],
        "doc_types": {"form": 3, "agreement": 2, "memo": 2, "motion": 1, "checklist": 1, "opinion letter": 1},
        "topics": {
            "revocable trust": ["revocable trust", "pour-over will", "successor trustee", "funding schedule", "incapacity provision", "trust restatement", "schedule of assets"],
            "trustee removal": ["trustee removal", "breach of trust", "trustee accounting", "surcharge", "trust protector", "petition for removal", "interim trustee"],
            "trust decanting": ["trust decanting", "second trust", "power to appoint", "beneficiary notice", "decanting memorandum", "situs change", "trust modification"],
            "probate petition": ["probate petition", "letters testamentary", "inventory and appraisal", "creditor claim", "notice to heirs", "final distribution", "personal representative"],
            "durable power of attorney": ["durable power of attorney", "attorney-in-fact", "springing power", "gifting authority", "health care directive", "agent certification", "successor agent"],
            "charitable remainder trust": ["charitable remainder trust", "unitrust amount", "remainder beneficiary", "donor advised fund", "payout rate", "charitable deduction", "term of years"],
            "family limited partnership": ["family limited partnership", "valuation discount", "general partner entity", "gift of units", "partnership appraisal", "transfer restrictions", "annual exclusion gift"],
            "beneficiary accounting": ["beneficiary accounting", "receipts and disbursements", "principal and income", "accounting period", "objection period", "trustee compensation", "informal accounting"],
        },
    },
}

# Slots: {doc} document label, {topic} topic title, {a} {b} topic terms,
# {mt} matter type, {forum}, {industry}, {n} a small number.
TOPIC_SENTENCES = [
    "The principal issue is {a}, with a secondary question about {b}.",
    "Section {n} sets out the negotiated position on {a} and the fallback on {b}.",
    "The drafting team reworked the language on {a} after comments from the other side.",
    "A comparison table tracks how {a} and {b} were handled in earlier rounds.",
    "The timetable in {forum} drove the order of work on {a}.",
    "Open points on {a} are listed at the end with proposed next steps.",
    "The client asked for a short explanation of {a} suitable for its board.",
    "Annex {n} reproduces the agreed wording for {a}.",
    "The team considered whether {a} should be dealt with separately from {b} and kept them together.",
    "The reviewing partner's comments on {a} have been incorporated.",
    "Background facts relevant to {a} are summarised in the first part.",
    "The treatment of {a} draws on the firm's earlier work for clients in the {industry} sector.",
    "Particular attention was given to {a} because of its effect on {b}.",
    "The other side's position on {a} is recorded together with our response.",
    "Alternatives to the current approach on {a} are described, including a simpler version relying on {b}.",
    "A defined term for {a} was added to avoid inconsistency with {b}.",
    "Items relating to {a} were confirmed complete before circulation.",
    "Where {a} interacts with {b}, the {doc} follows the structure used in the firm's standard.",
    "Timing, responsibility and sign-off for {a} are allocated in the table.",
    "The {mt} context shaped how {a} was presented.",
    "Earlier drafts treated {a} more briefly; this version expands it.",
    "A worked example of {a} is included for the client team.",
    "The section on {a} cross-refers to the discussion of {b}.",
    "Notes from the call on {a} are attached for the file.",
]
OPENING_SENTENCES = [
    "This {doc} addresses {topic} in connection with the {mt} matter.",
    "This {doc} was prepared for the {mt} matter and concerns {topic}.",
    "Subject: {topic}. Prepared in the course of the {mt} matter in {forum}.",
    "The purpose of this {doc} is to record the position on {topic}.",
]
OPENING_WITHOUT_TOPIC = [
    "This {doc} was prepared in the course of the {mt} matter.",
    "Prepared for the client team on the {mt} matter in {forum}.",
]
GENERIC_SENTENCES = [
    "This version supersedes drafts circulated earlier.",
    "Capitalised terms have the meanings given in the main document.",
    "Comments are requested by the end of the week.",
    "The document is subject to partner review before it is sent out.",
    "Nothing in this document should be shared outside the client team.",
    "A redline against the prior version accompanies this draft.",
    "The assumptions and the documents reviewed are listed in the appendix.",
    "Please raise any factual corrections with the responsible associate.",
    "A short summary for non-specialists appears at the front.",
    "Dates and amounts remain to be confirmed with the client.",
    "The format follows the practice group's house style.",
    "Billing narrative and matter number appear on the cover sheet.",
]
CROSS_SENTENCES = [
    "A related point on {x} is noted but not developed here.",
    "For {x}, see the separate document on that subject.",
    "This does not cover {x}, which is handled elsewhere in the file.",
]

# Queries phrased in words the corpus does not use. Keyword search is expected
# to do badly on these; they are in the answer key so the reported numbers
# show that limit instead of hiding it.
MISMATCH_QUERIES = [
    ("emp", "non-compete covenant", "restraint on joining a rival after resignation {type}"),
    ("re", "lease assignment and subletting", "handing premises over to a new occupier {type}"),
    ("corp", "earn-out provisions", "deferred price contingent on future performance {type}"),
    ("lit", "expert exclusion", "keeping the opposing specialist witness out {type}"),
    ("fin", "forbearance agreement", "bank agrees to hold off after missed payments {type}"),
    ("priv", "data breach notification", "telling customers about a hacking incident {type}"),
]
