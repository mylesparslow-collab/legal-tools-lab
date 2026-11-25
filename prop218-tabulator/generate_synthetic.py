"""Builds the fictional sample proceeding. Every name, parcel, and address is invented.
APN books start with 9 so they cannot be mistaken for a real county roll. Seeded, so
the output is the same on every run."""
import csv, json, random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "sample_data"
R = random.Random(218)
FIRST = "Daniel Priya Marisol Kenji Abena Tomas Ingrid Wendell Farah Luca Noor Callum Yara Desmond Ines Rafael Sunita Gideon Leilani Otto Mireille Bashir Tamsin Hollis Renata Cyrus Odalys Thaddeus Zofia Emeka".split()
LAST = "Okafor Varga Lindqvist Castellanos Nakagawa Abernathy Petrosyan Mwangi Fairweather Ostrowski Delacroix Yamane Halvorsen Quintero Rasmussen Achterberg Bellweather Tanaka Ndiaye Kowalczyk Sorrento Whitlock Marchetti Oyelaran Thistlewood".split()
STREETS = ["Alder", "Marlow Creek", "Quarry", "Heron", "Tannery", "Juniper", "Mill Race", "Osprey", "Larkspur", "Foundry"]
TYPES = ["Street", "Avenue", "Road", "Lane", "Court", "Drive"]

def person():
    return "%s %s" % (R.choice(FIRST), R.choice(LAST))

def write(name, rows, cols):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

def main():
    OUT.mkdir(exist_ok=True)
    parcels, accounts = [], []
    for i in range(1, 413):
        apn = "9%02d-%03d-%03d" % (1 + i // 100, 10 + (i % 100) // 10, i % 10 + 1)
        k = R.random()
        if 20 <= i <= 22:
            owners = ["Heron Lane Holdings LLC"]
        elif k < 0.6:
            owners = [person()]
        elif k < 0.85:
            ln = R.choice(LAST); owners = ["%s %s" % (a, ln) for a in R.sample(FIRST, 2)]
        else:
            owners = ["%s Family Trust" % R.choice(LAST)]
        situs = "%d %s %s" % (100 + i * 3, R.choice(STREETS), R.choice(TYPES))
        parcels.append({"apn": apn, "situs_address": situs, "record_owners": "|".join(owners),
                        "identified": "N" if i > 400 else "Y"})
        if i > 400:
            continue
        tenant = R.random() < 0.3
        accounts.append({"account_no": "MC-%05d" % (10000 + i), "apn": apn,
                         "customer_name": person() if tenant else owners[0],
                         "customer_role": "tenant" if tenant else "owner", "service_address": situs})
        if i % 16 == 0:
            accounts.append({"account_no": "MC-%05d" % (20000 + i), "apn": apn, "customer_name": person(),
                             "customer_role": "tenant", "service_address": situs + " Unit B"})
    write("parcels.csv", parcels, ["apn", "situs_address", "record_owners", "identified"])
    write("accounts.csv", accounts, ["account_no", "apn", "customer_name", "customer_role", "service_address"])

    acct = {}
    for a in accounts:
        acct.setdefault(a["apn"], []).append(a)
    subs, n = [], [0]
    def day(lo=5, hi=62):
        d = R.randint(lo, hi); m, dd = (8, 3 + d) if d <= 28 else ((9, d - 28) if d <= 58 else (10, d - 58))
        return "2026-%02d-%02dT%02d:%02d:00" % (m, dd, R.randint(9, 16), R.choice([0, 15, 30, 45]))
    def sub(signer, apn="", account="", address="", received=None, channel=None, signed="Y",
            action="protest", text="", triage=""):
        n[0] += 1
        subs.append({"submission_id": "S-%04d" % n[0], "received": received or day(),
                     "channel": channel or R.choice(["mail", "mail", "mail", "hand_delivery"]),
                     "signer_name": signer, "apn_as_written": apn, "account_no": account,
                     "service_address": address, "signed": signed, "action": action,
                     "letter_text": text, "objection_triage": triage})
        return subs[-1]
    def fmt(apn):
        return R.choice([apn, apn, apn.replace("-", " "), apn.replace("-", ""), apn + " "])
    def owner_of(p):
        o = p["record_owners"].split("|")[0]
        return o if "Trust" not in o and "LLC" not in o else None

    ident = parcels[:400]
    pool = [p for p in ident if owner_of(p)]
    R.shuffle(pool)
    it = iter(pool)
    take = lambda k: [next(it) for _ in range(k)]

    for p in take(104):                                   # ordinary valid protests
        who = R.choice([owner_of(p), acct[p["apn"]][0]["customer_name"]])
        sub(who, fmt(p["apn"]))
    for p in take(12):                                    # owner and tenant both protest
        sub(owner_of(p), fmt(p["apn"])); sub(acct[p["apn"]][0]["customer_name"], fmt(p["apn"]))
    co = [p for p in ident if "|" in p["record_owners"]][:8]
    for p in co:                                          # both co-owners protest
        for o in p["record_owners"].split("|"):
            sub(o, fmt(p["apn"]))
    for p in take(6):                                     # same person twice
        sub(owner_of(p), fmt(p["apn"])); sub(owner_of(p), fmt(p["apn"]))
    for p in take(10):                                    # account number only
        a = acct[p["apn"]][0]; sub(a["customer_name"], account=a["account_no"].lower())
    for p in take(8):                                     # address only
        a = acct[p["apn"]][0]; sub(a["customer_name"], address=a["service_address"].replace("Street", "St").replace("Avenue", "Ave."))
    for p in take(3):
        sub(owner_of(p))                                  # nothing to identify the parcel
    for p in take(2):
        sub(owner_of(p), account="MC-99%03d" % R.randint(0, 999))
    for p in take(5):
        sub(owner_of(p), fmt(p["apn"]), signed="N")
    for p in take(4):
        sub(owner_of(p), fmt(p["apn"]), received="2026-10-0%dT%02d:10:00" % (R.choice([6, 7]), 21))
    for p in take(6):
        sub(owner_of(p), fmt(p["apn"]), channel="email")
    for p in take(3):
        sub(owner_of(p), fmt(p["apn"]), channel="oral", received="2026-10-06T19:%02d:00" % R.randint(10, 50))
    for p in take(7):
        sub(person() + " Jr.", fmt(p["apn"]))             # not on roll or account
    wd = take(5)
    for j, p in enumerate(wd):                            # withdrawals
        sub(owner_of(p), fmt(p["apn"]), received="2026-08-2%dT10:00:00" % j)
        sub(owner_of(p), fmt(p["apn"]), received="2026-09-1%dT10:00:00" % j, action="withdraw")
    sub(owner_of(wd[0]), fmt(wd[0]["apn"]), received="2026-10-06T19:05:00", channel="hearing_written")
    sub("Heron Lane Holdings LLC", "; ".join(p["apn"] for p in parcels[19:22]))
    for p in parcels[400:404]:
        sub(p["record_owners"].split("|")[0], fmt(p["apn"]))
    sub(person(), "955-001-001"); sub(person(), "956 002 003")

    letters = [
        ("The top tier price is not proportional to the cost of service for my parcel.", "objection:OBJ-001"),
        ("Charging hydrant costs to residential meters violates Proposition 218.", "objection:OBJ-002"),
        ("I protest. Rates are too high for people on fixed incomes.", ""),
        ("The peaking factors in the study are not supported by any data.", "objection:OBJ-003"),
        ("This is illegal and I protest.", "bare_protest"),
        ("Tier 3 subsidizes the recycled water program, which I do not receive.", ""),
        ("The methodology shifts commercial costs to homes. Article XIII D forbids that.", ""),
        ("No more increases.", ""),
    ]
    for s, (text, triage) in zip([x for x in subs if x["action"] == "protest" and x["received"] < "2026-09-15"][:8], letters):
        s["letter_text"], s["objection_triage"] = text, triage
    write("submissions.csv", subs, list(subs[0].keys()))

    tags = ["tiered rates; proportionality", "hydrant costs (§ 53750.5)", "peaking factors (§ 53750.6)",
            "reserve funding", "tiered rates; conservation pricing", "notice content", "capital plan costs",
            "customer class allocation", "drought surcharge", "tiered rates", "meter charge"]
    obj, resp = [], []
    for j, tag in enumerate(tags, 1):
        late = j in (10, 11)
        obj.append({"objection_id": "OBJ-%03d" % j,
                    "received": "2026-09-2%dT11:00:00" % (j - 5) if late else "2026-09-%02dT14:30:00" % (j * 2),
                    "submitter": person(), "issue_tags": tag,
                    "grounds_text": "" if j == 6 else "Objects that the proposed rates do not comply with art. XIII D § 6(b) as to %s." % tag.split(";")[0]})
        if late or j == 7:
            continue
        resp.append({"objection_id": "OBJ-%03d" % j,
                     "responded_at": "2026-10-07T09:00:00" if j == 9 else "2026-09-30T16:00:00",
                     "author": "District engineer and general counsel", "exhibit_ref": "Res. 2026-14, Exh. C-%d" % j,
                     "explains_substantive_basis": "Y",
                     "presented_to_board_at": "2026-10-07T09:00:00" if j == 9 else "2026-10-06T18:05:00"})
    write("objections.csv", obj, list(obj[0].keys()))
    write("responses.csv", resp, list(resp[0].keys()))

    case = {
        "agency": "Marlow Creek Water District (fictional)", "proceeding": "section_6_fee", "service": "water",
        "notice_mailed": "2026-08-03", "hearing_date": "2026-10-06", "hearing_close": "2026-10-06T20:30:00",
        "adoption_date": "2026-10-06", "effective_date": "2027-01-01",
        "ab2257": {
            "proposed_fee_available": "2026-08-03", "objection_deadline": "2026-09-21T17:00:00",
            "notice": {"written_basis_on_website": True, "website_link_in_notice": True,
                       "exhaustion_statement_prominent": True, "objection_requirements_stated": True,
                       "sol_120_day_statement": True},
            "written_basis_mail_requests": [
                {"requester": "Resident A", "requested": "2026-08-11", "mailed": "2026-08-12"},
                {"requester": "Resident B", "requested": "2026-09-02", "mailed": "2026-09-03"}]},
        "policy": {"accepted_channels": ["mail", "hand_delivery", "hearing_written"],
                   "require_signature": True, "allow_withdrawal": True},
        "record_documents": [
            {"category": "A", "title": "2026 Water Cost-of-Service Study"}, {"category": "A", "title": "Staff report, Oct. 6, 2026"},
            {"category": "B", "title": "Minutes, Finance Committee, July 14, 2026"},
            {"category": "C", "title": "Prop 218 notice mailed Aug. 3, 2026"},
            {"category": "D", "title": "Objections OBJ-001 to OBJ-011 and responses"},
            {"category": "F", "title": "Draft Resolution 2026-14"},
            {"category": "G", "title": "Protest audit log and tabulation"},
            {"category": "H", "title": "Capital improvement plan 2027-2031"}]}
    (OUT / "case.json").write_text(json.dumps(case, indent=2), encoding="utf-8")

    # Small § 4 assessment example.
    ap, ab = [], []
    for i in range(1, 25):
        apn = "970-100-%03d" % i
        two = i % 4 == 0
        ap.append({"apn": apn, "assessment_cents": R.choice([42000, 61500, 88000, 125000, 310000]),
                   "owners": ("%s:1/2|%s:1/2" % (person(), person())) if two else (("%s|%s" % (person(), person())) if i == 23 else person())})
    k = 0
    for p in ap:
        for part in p["owners"].split("|"):
            if R.random() < 0.7 or p["apn"].endswith("023"):
                k += 1
                ab.append({"ballot_id": "B-%03d" % k, "received": "2026-09-%02dT10:00:00" % R.randint(1, 28), "apn": p["apn"],
                           "owner_name": part.split(":")[0], "vote": R.choice(["yes", "no", "no"]), "signed": "N" if k == 5 else "Y"})
    ab.append({"ballot_id": "B-900", "received": "2026-10-01T10:00:00", "apn": ab[0]["apn"], "owner_name": ab[0]["owner_name"],
               "vote": "yes" if ab[0]["vote"] == "no" else "no", "signed": "Y"})
    (OUT / "assessment").mkdir(exist_ok=True)
    with open(OUT / "assessment" / "parcels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ap[0].keys())); w.writeheader(); w.writerows(ap)
    with open(OUT / "assessment" / "ballots.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ab[0].keys())); w.writeheader(); w.writerows(ab)
    print("parcels %d, accounts %d, submissions %d, objections %d" % (len(parcels), len(accounts), len(subs), len(obj)))

if __name__ == "__main__":
    main()
