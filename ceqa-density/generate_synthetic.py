"""Writes fictional sample data (seed-fixed, so output is identical on every run).
Nothing here is a real case, agency, project, person or parcel."""
import csv, json, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SD = ROOT / "sample_data"; DOCS = SD / "docs"
random.seed(21167)

CITY = "City of Calder Bay"
PROJECT = "Harborview Commons Mixed-Use Project"
PHRASES = ["traffic counts along Tidewater Avenue", "the stormwater basin at the north parcel line", "construction noise near Marsh Elementary",
           "the shade study for the plaza", "cumulative air quality modeling", "the revised site plan dated in the application",
           "the wetland buffer along Tidewater Marsh", "the transportation demand management plan", "the water supply assessment",
           "tribal cultural resource monitoring", "the alternatives analysis", "the parking and loading plan", "the geotechnical report"]
VERBS = ["Staff reviewed", "The consultant updated", "The applicant resubmitted", "The commenter questioned", "The department confirmed",
         "The memo summarizes", "The analysis addresses", "The response clarifies"]

def body(title, author, date, pages, salt):
    r = random.Random(f"{salt}{title}")
    out = [f"{title}", f"{CITY} - {PROJECT}", f"Author: {author}    Date: {date}", "FICTIONAL SAMPLE DOCUMENT", ""]
    for i in range(pages * 9):
        s = " ".join(f"{r.choice(VERBS)} {r.choice(PHRASES)} and {r.choice(PHRASES)}." for _ in range(4))
        out += [f"{i + 1}. {s}", ""]
    return "\n".join(out)

# doc_type -> (rule 3.2205(a)(1) group, 21167.6(e) category)
T = {"notice_of_determination": ("A", 5), "resolution": ("B", 9), "ceqa_findings": ("C", 9), "final_eir": ("D", 9), "draft_eir": ("D", 10),
     "initial_study": ("E", 10), "staff_report": ("F", 2), "minutes": ("G", 4), "transcript": ("G", 4), "application": ("H", 1),
     "notice": ("H", 5), "comment_letter": ("H", 6), "correspondence": ("H", 7), "proposed_findings": ("H", 8), "study": ("H", 10),
     "internal_email": ("H", 10), "internal_memo": ("H", 10), "staff_notes": ("H", 10), "admin_draft": ("H", 10)}
# title, type, date, author, recipient, pages, then flags
ROWS = [
 ("Notice of Determination", "notice_of_determination", "2026-09-18", "Planning Division", "County Clerk", 2, {}),
 ("Resolution No. 2026-41 certifying the Final EIR", "resolution", "2026-09-15", "City Council", "", 4, {}),
 ("Resolution No. 2026-42 approving the project", "resolution", "2026-09-15", "City Council", "", 5, {}),
 ("CEQA Findings and Statement of Overriding Considerations", "ceqa_findings", "2026-09-15", "City Council", "", 18, {}),
 ("Final Environmental Impact Report", "final_eir", "2026-08-20", "Estuary Environmental Consulting", CITY, 96, {}),
 ("Draft Environmental Impact Report", "draft_eir", "2026-03-02", "Estuary Environmental Consulting", CITY, 74, {}),
 ("Initial Study", "initial_study", "2025-10-06", "Planning Division", "", 22, {}),
 ("Planning Commission staff report", "staff_report", "2026-08-27", "R. Okafor, Senior Planner", "Planning Commission", 14, {}),
 ("City Council staff report", "staff_report", "2026-09-15", "R. Okafor, Senior Planner", "City Council", 16, {}),
 ("Planning Commission minutes", "minutes", "2026-08-27", "Commission Secretary", "", 6, {}),
 ("City Council hearing transcript", "transcript", "2026-09-15", "City Clerk", "", 31, {}),
 ("Project application and plan set", "application", "2025-08-11", "Tidewater Housing Partners LLC", "Planning Division", 28, {}),
 ("Notice of Preparation", "notice", "2025-10-20", "Planning Division", "State Clearinghouse", 3, {}),
 ("Notice of Availability of Draft EIR", "notice", "2026-03-02", "Planning Division", "", 2, {}),
 ("Notice of public hearing", "notice", "2026-09-01", "City Clerk", "", 1, {}),
 ("Comment letter on Draft EIR", "comment_letter", "2026-04-10", "Friends of Tidewater Marsh", "Planning Division", 9, {}),
 ("Comment letter on Draft EIR", "comment_letter", "2026-04-14", "Calder Bay Unified School District", "Planning Division", 4, {}),
 ("Comment letter on Draft EIR", "comment_letter", "2026-04-15", "Regional Water Board staff", "Planning Division", 5, {}),
 ("Letter transmitting revised traffic study", "correspondence", "2026-06-03", "Tidewater Housing Partners LLC", "Planning Division", 3, {}),
 ("Letter to applicant requesting additional information", "correspondence", "2025-09-12", "Planning Division", "Tidewater Housing Partners LLC", 2, {}),
 ("Applicant's proposed findings", "proposed_findings", "2026-09-08", "Tidewater Housing Partners LLC", "City Council", 7, {}),
 ("Transportation impact study", "study", "2026-01-22", "Gridline Traffic Engineers", "Planning Division", 26, {}),
 ("Biological resources technical report", "study", "2026-01-30", "Estuary Environmental Consulting", "Planning Division", 19, {}),
 ("Internal memo: wetland buffer recommendation", "internal_memo", "2026-05-19", "M. Castellanos, Public Works", "R. Okafor", 3, {"internal": 1}),
 ("Email: draft response to school district comment", "internal_email", "2026-05-06", "R. Okafor", "M. Castellanos", 1, {"internal": 1, "electronic": 1}),
 ("Email: traffic count discrepancy", "internal_email", "2026-05-22", "M. Castellanos", "R. Okafor", 1, {"internal": 1, "electronic": 1}),
 ("Email: questions on shade study", "internal_email", "2026-06-11", "J. Lindqvist, Associate Planner", "R. Okafor", 1, {"internal": 1, "electronic": 1}),
 ("Email: mitigation measure wording, forwarded to City Manager", "internal_email", "2026-07-02", "R. Okafor", "D. Abara, City Manager", 2, {"internal": 1, "electronic": 1, "reviewed_by": "lead_agency_executive"}),
 ("Email: buffer width options, reviewed by Planning Director", "internal_email", "2026-07-09", "J. Lindqvist", "P. Navarrete, Planning Director", 1, {"internal": 1, "electronic": 1, "reviewed_by": "supervisory_official"}),
 ("Email: staff summary attached to Council packet", "internal_email", "2026-09-10", "R. Okafor", "City Clerk", 2, {"internal": 1, "electronic": 1, "presented": 1}),
 ("Email: meeting invitation, EIR kickoff", "internal_email", "2025-10-01", "J. Lindqvist", "Project team", 1, {"internal": 1, "electronic": 1, "logistical": 1}),
 ("Email: reschedule Thursday check-in", "internal_email", "2026-02-17", "J. Lindqvist", "Project team", 1, {"internal": 1, "electronic": 1, "logistical": 1}),
 ("Handwritten staff notes from site visit", "staff_notes", "2025-11-14", "J. Lindqvist", "", 2, {"internal": 1, "staff_notes": 1}),
 ("Email: City Attorney advice on recirculation", "internal_email", "2026-06-25", "Office of the City Attorney", "R. Okafor", 1, {"internal": 1, "electronic": 1, "privilege": "attorney_client"}),
 ("Memo: litigation risk assessment", "internal_memo", "2026-08-05", "Office of the City Attorney", "City Council", 4, {"internal": 1, "privilege": "attorney_client"}),
 ("Email: pre-decisional policy options", "internal_email", "2026-07-21", "P. Navarrete", "D. Abara", 1, {"internal": 1, "electronic": 1, "privilege": "deliberative_process"}),
 ("Administrative draft EIR (not released)", "admin_draft", "2026-01-12", "Estuary Environmental Consulting", "Planning Division", 30, {"draft": 1}),
 ("Email from applicant: schedule for response to comments", "correspondence", "2026-05-01", "Tidewater Housing Partners LLC", "R. Okafor", 1, {"electronic": 1}),
 ("Email from resident opposing project", "comment_letter", "2026-09-12", "A. Whitcombe", "City Council", 1, {"electronic": 1}),
]
DUPES = [15, 21, 25]  # indexes of rows exported twice (mailbox export plus shared-drive copy)

def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    for f in DOCS.glob("*.txt"):
        f.unlink()
    out = []
    for i, (title, typ, date, author, rcpt, pages, fl) in enumerate(ROWS, 1):
        did = f"CB-{i:04d}"
        (DOCS / f"{did}.txt").write_text(body(title, author, date, pages, did))
        g, cat = T[typ]
        out.append({"doc_id": did, "date": date, "title": title, "author": author, "recipient": rcpt, "doc_type": typ, "e_category": cat,
                    "rule_group": g, "internal_agency_comm": "Y" if fl.get("internal") else "N", "electronic": "Y" if fl.get("electronic") else "N",
                    "staff_notes": "Y" if fl.get("staff_notes") else "N", "logistical": "Y" if fl.get("logistical") else "N",
                    "presented_to_decisionmaking_body": "Y" if fl.get("presented") else "N", "reviewed_by": fl.get("reviewed_by", "none"),
                    "privilege_flag": fl.get("privilege", "none"), "draft_env_doc": "Y" if fl.get("draft") else "N",
                    "released_for_public_review": "N", "file": f"docs/{did}.txt"})
    for n, idx in enumerate(DUPES, 1):
        src = dict(out[idx]); did = f"CB-D{n:03d}"
        (DOCS / f"{did}.txt").write_bytes((DOCS / f"{src['doc_id']}.txt").read_bytes())
        src.update(doc_id=did, file=f"docs/{did}.txt", title=src["title"] + " (shared-drive copy)")
        out.append(src)
    with open(SD / "documents.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)

    case = {"case_name": "Friends of Tidewater Marsh v. City of Calder Bay", "court": "Superior Court of California, County of Santa Lucinda (fictional)",
            "case_number": "26-CEQA-00417 (fictional)", "filed": "2026-10-16", "request_served": "2026-10-23", "as_of": "2026-11-25",
            "record_preparer": "agency", "extensions": [],
            "project": {"name": PROJECT, "description": "312 apartments over ground-floor retail on a 6.1-acre former boatyard",
                        "includes_warehouse_distribution_center": False, "distribution_center_sqft": 0, "includes_oil_gas_infrastructure": False}}
    (SD / "record_case.json").write_text(json.dumps(case, indent=1))
    dc = json.loads(json.dumps(case))
    dc.update(case_name="Friends of Tidewater Marsh v. City of Calder Bay (Eastgate Logistics Center)", case_number="26-CEQA-00418 (fictional)",
              extensions=[{"type": "stipulation", "days": 30}])
    dc["project"].update(name="Eastgate Logistics Center", description="640,000 sq ft warehouse distribution center (same document set reused to show the other branch)",
                         includes_warehouse_distribution_center=True, distribution_center_sqft=640000)
    (SD / "record_case_distribution_center.json").write_text(json.dumps(dc, indent=1))

    site_common = {"owner_type": "religious_institution", "owner_acquired": "1987-04-02", "as_of": "2026-11-25", "pct_lower_or_below": 80, "pct_moderate": 20, "pct_staff": 0,
                   "adjoins_light_industrial": False, "ft_to_heavy_industrial": 4100, "ft_to_title_v": 6800, "ft_to_oil_gas": 25000, "multifamily_permitted": False,
                   "zone_allows_residential": False, "jurisdiction_type": "metropolitan", "site_acres": 2.4, "builders_remedy": False, "in_city_or_urban_area": True,
                   "previously_urban_use": True, "perimeter_urban_pct": 88, "quarter_mile_urban_pct": 81, "consistent_with_plan_zoning": True,
                   "demolishes_historic": False, "includes_transient_lodging": False, "application_complete": "2027-01-11", "tribe_accepted": "2027-02-08", "tribal_extension": False}
    sb4 = {"site": {"name": "Calder Bay Community Fellowship, surplus parking lot", **site_common, "proposed_density_du_ac": 40},
           "calc": {"site_acres": 2.4, "zoning_density_du_ac": 0, "sb4_applies": True, "base_path": "AFF100", "base_affordable_units": 96, "aff100_moderate_units": 19,
                    "add_path": "NONE", "add_units": 0, "near_major_transit": False, "share_0_1_br": 0.5, "share_2_3_br": 0.45, "share_4plus_br": 0.05, "avg_bedrooms_per_unit": 1.7}}
    mixed = {"site": {"name": "Harborview Commons, Parcel B", **site_common, "owner_type": "private_developer", "owner_acquired": "2024-06-30", "pct_lower_or_below": 15, "pct_moderate": 15,
                      "zone_allows_residential": True, "multifamily_permitted": True, "proposed_density_du_ac": 40},
             "calc": {"site_acres": 2.4, "zoning_density_du_ac": 40, "sb4_applies": False, "base_path": "VLI", "base_affordable_units": 15, "aff100_moderate_units": 0,
                      "add_path": "MOD", "add_units": 15, "near_major_transit": True, "share_0_1_br": 0.6, "share_2_3_br": 0.4, "share_4plus_br": 0.0, "avg_bedrooms_per_unit": 1.5}}
    (SD / "site_sb4.json").write_text(json.dumps(sb4, indent=1)); (SD / "site_mixed_income.json").write_text(json.dumps(mixed, indent=1))
    print(f"wrote {len(out)} documents, 2 record cases, 2 sites")

if __name__ == "__main__":
    main()
