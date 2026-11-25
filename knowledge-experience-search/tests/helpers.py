"""A small hand-built world used by the unit tests. All invented."""
from kx import index
from kx.schema import (Document, Grant, Matter, Person, TeamMember, TimeEntry, Wall)
from sources.memory import MemoryAdapter

AS_OF = "2026-06-30"

FILLER = ("The drafting team reworked the language after comments from the other side. "
          "A comparison table tracks how the points were handled in earlier rounds. "
          "Open points are listed at the end with proposed next steps. "
          "The reviewing partner's comments have been incorporated in this version. "
          "Background facts are summarised in the first part for the client team.")


def body(*sentences):
    return " ".join(sentences) + " " + FILLER


def people():
    return [
        Person("alice", "Alice Varrowby", "Caldmoor", "Corporate", "Partner", "active"),
        Person("bob", "Bob Tindlewick", "Caldmoor", "Corporate", "Associate", "active"),
        Person("carol", "Carol Okonmere", "Estermere", "Litigation", "Partner", "active"),
        Person("dave", "Dave Quistrel", "Estermere", "Corporate", "Partner", "departed"),
        Person("erin", "Erin Wrenfold", "Senna Bay", "Tax", "Associate", "active"),
    ]


def matters():
    return [
        Matter("M_PUB", "Thessaby Works: asset purchase", "C1", "software", "Corporate",
               "asset purchase", "State of Caldmoor", "Caldmoor", "2024-01-10", "2024-09-01",
               "Asset purchase centred on earn-out provisions.", "public"),
        Matter("M_PUB2", "Dovrane Group: contract dispute", "C2", "retail", "Litigation",
               "contract dispute", "Tavish County", "Estermere", "2023-02-01", "2023-12-01",
               "Contract dispute centred on forum selection clause.", "public"),
        Matter("M_RES", "Project Lodestar", "C3", "energy", "Corporate", "merger",
               "State of Wenrick", "Caldmoor", "2025-01-05", "", "Merger for an energy client.",
               "restricted"),
        Matter("M_WALL", "Project Zephyrine", "C4", "aerospace", "Corporate", "asset purchase",
               "Province of Sennamar", "Estermere", "2025-03-01", "",
               "Asset purchase centred on earn-out provisions.", "public"),
        Matter("M_RW", "Project Zephyrine financing", "C4", "aerospace", "Corporate",
               "acquisition finance", "Province of Sennamar", "Estermere", "2025-04-01", "",
               "Financing for the same client.", "restricted"),
        Matter("M_UNK", "Unclassified matter", "C5", "retail", "Tax", "tax controversy",
               "Aldhaven Tax Tribunal", "Senna Bay", "2022-01-01", "", "Unknown security.",
               "CONFIDENTIAL-7"),
    ]


def documents():
    earn = body("This memo addresses earn-out provisions in connection with the asset purchase.",
                "The principal issue is the earn-out milestone payment and the revenue target.")
    return [
        Document("d_pub_1", "M_PUB", "Memo: earn-out provisions", earn, "memo", "alice",
                 "2024-03-01", is_final=True, modified="2024-03-01T00:00:00"),
        Document("d_pub_2", "M_PUB", "Checklist: closing deliverables",
                 body("Closing checklist with officer certificate and signature pages.",
                      "A related point on earn-out is noted but not developed here."),
                 "checklist", "bob", "2024-08-20", is_final=True, modified="2024-08-20T00:00:00"),
        Document("d_pub_3", "M_PUB2", "Motion: forum selection clause",
                 body("This motion addresses the forum selection clause and transfer of venue.",
                      "Section 4 sets out the position on improper venue."),
                 "motion", "carol", "2023-06-15", is_final=True, was_filed=True,
                 modified="2023-06-15T00:00:00"),
        Document("d_res_1", "M_RES", "Agreement: earn-out provisions for the merger",
                 body("This agreement addresses earn-out provisions for the merger.",
                      "Annex 2 reproduces the agreed wording for the acceleration event."),
                 "agreement", "alice", "2025-02-11", is_final=True, modified="2025-02-11T00:00:00"),
        Document("d_wall_1", "M_WALL", "Project Zephyrine - Memo: earn-out provisions",
                 body("This memo addresses earn-out provisions. Internal reference: Project Zephyrine.",
                      "The earn-out period and the set-off right were the main earn-out points."),
                 "memo", "carol", "2025-05-02", is_final=True, model_form=True, reuse_count=12,
                 modified="2025-05-02T00:00:00"),
        # A near-duplicate of the open memo d_pub_1, sitting behind the wall.
        Document("d_wall_2", "M_WALL", "Memo: earn-out provisions (adapted)",
                 earn.replace("principal", "main"), "memo", "carol", "2025-05-20", is_final=True,
                 modified="2025-05-20T00:00:00"),
        Document("d_rw_1", "M_RW", "Agreement: zephyrine side letter",
                 body("This agreement records the side letter for Project Zephyrine.",
                      "Timing and sign-off for the guaranty are allocated in the table."),
                 "agreement", "carol", "2025-06-01", is_final=True, modified="2025-06-01T00:00:00"),
        Document("d_unk_1", "M_UNK", "Memo: quasar audit defence",
                 body("This memo addresses the quasar audit defence and the protest letter."),
                 "memo", "erin", "2022-05-05", is_final=True, modified="2022-05-05T00:00:00"),
        Document("d_fam_v1", "M_PUB", "Form: severance agreement",
                 body("This form addresses the severance agreement and the release of claims.",
                      "Early draft with the consideration period left open."),
                 "form", "bob", "2024-04-01", family_id="FAM1", version_no=1, is_final=False,
                 modified="2024-04-01T00:00:00"),
        Document("d_fam_v2", "M_PUB", "Form: severance agreement",
                 body("This form addresses the severance agreement and the release of claims.",
                      "The consideration period and revocation period are now settled."),
                 "form", "bob", "2024-04-20", family_id="FAM1", version_no=2, is_final=True,
                 modified="2024-04-20T00:00:00"),
    ]


def adapter(**overrides):
    kwargs = dict(
        people=people(), matters=matters(),
        group_members=[("g_corp", "alice"), ("g_corp", "bob"), ("g_lit", "carol")],
        grants=[Grant("M_RES", "user", "alice"), Grant("M_RES", "group", "g_lit"),
                Grant("M_RW", "group", "g_corp"), Grant("M_RW", "user", "carol")],
        walls=[Wall("W1", ("M_WALL", "M_RW"), ("bob",))],
        team=[TeamMember("M_PUB", "alice", "lead"), TeamMember("M_PUB", "bob", "support"),
              TeamMember("M_PUB2", "carol", "lead"), TeamMember("M_RES", "alice", "lead"),
              TeamMember("M_WALL", "carol", "lead"), TeamMember("M_WALL", "dave", "support"),
              TeamMember("M_RW", "carol", "lead")],
        time_entries=[
            TimeEntry("t1", "M_PUB", "alice", "2024-03-01", 30.0),
            TimeEntry("t2", "M_PUB", "bob", "2024-08-20", 12.5),
            TimeEntry("t3", "M_PUB2", "carol", "2023-06-15", 25.0),
            TimeEntry("t4", "M_RES", "alice", "2025-02-11", 18.0),
            TimeEntry("t5", "M_WALL", "carol", "2026-05-02", 40.0),
            TimeEntry("t6", "M_WALL", "dave", "2025-05-10", 9.0),
            TimeEntry("t7", "M_RW", "carol", "2025-06-01", 6.0),
            TimeEntry("t8", "M_PUB", "erin", "2024-05-01", 2.0),
        ],
        documents=documents())
    kwargs.update(overrides)
    return MemoryAdapter(**kwargs)


def build(source=None, **indexer_kwargs):
    """Index a source into an in-memory database. Returns (conn, indexer, source)."""
    source = source or adapter()
    conn = index.connect(":memory:")
    indexer = index.Indexer(conn, **indexer_kwargs)
    indexer.sync(source, full=True)
    return conn, indexer, source


def all_doc_ids(result):
    """Every document id that appears anywhere in a search result."""
    ids = set()
    for r in result["results"]:
        ids.add(r["doc_id"])
        ids.update(v["doc_id"] for v in r["other_versions"])
        ids.update(v["doc_id"] for v in r["near_duplicates"])
    return ids
