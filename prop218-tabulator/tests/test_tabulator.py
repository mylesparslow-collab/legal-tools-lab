import copy, json, sys, unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tabulator as t

RULES = t.load_rules()
CLOSE = datetime(2026, 10, 6, 20, 30)


def parcels(n):
    return [{"apn": "900-000-%03d" % i, "situs_address": "%d Test Road" % i,
             "record_owners": "Owner Number%d" % i, "identified": "Y"} for i in range(1, n + 1)]


def sub(i, signer, apn="", **kw):
    d = {"submission_id": "S-%03d" % i, "received": "2026-09-01T10:%02d:00" % (i % 60), "channel": "mail",
         "signer_name": signer, "apn_as_written": apn, "account_no": "", "service_address": "",
         "signed": "Y", "action": "protest", "letter_text": "", "objection_triage": ""}
    d.update(kw)
    return d


def tally(p, s, accounts=()):
    return t.tally_fee_protests(p, list(accounts), s, CLOSE, RULES)


def statuses(r):
    return [l.status for l in r["lines"]]


class Threshold(unittest.TestCase):
    def test_majority_is_more_than_half(self):
        self.assertEqual([t.majority_threshold(n) for n in (1, 2, 3, 100, 101, 400)], [1, 2, 2, 51, 51, 201])

    def test_exactly_half_is_not_a_majority(self):
        p = parcels(10)
        r = tally(p, [sub(i, "Owner Number%d" % i, "900-000-%03d" % i) for i in range(1, 6)])
        self.assertEqual((r["counted_protests"], r["outcome"]), (5, "NO_MAJORITY_PROTEST"))
        r = tally(p, [sub(i, "Owner Number%d" % i, "900-000-%03d" % i) for i in range(1, 7)])
        self.assertEqual((r["counted_protests"], r["outcome"]), (6, "MAJORITY_PROTEST"))

    def test_denominator_is_identified_parcels_not_protests(self):
        p = parcels(9)
        p[8]["identified"] = "N"
        r = tally(p, [sub(1, "Owner Number9", "900-000-009")])
        self.assertEqual((r["identified_parcels"], r["threshold"], r["counted_protests"]), (8, 5, 0))
        self.assertEqual(statuses(r), ["NOT_COUNTED"])


class Dedupe(unittest.TestCase):
    ACCT = [{"account_no": "A-1", "apn": "900-000-001", "customer_name": "Tina Tenant",
             "customer_role": "tenant", "service_address": "1 Test Road"}]

    def test_owner_and_tenant_count_once(self):
        r = tally(parcels(3), [sub(1, "Owner Number1", "900-000-001"), sub(2, "Tina Tenant", "900 000 001")], self.ACCT)
        self.assertEqual(r["counted_protests"], 1)
        self.assertEqual(statuses(r), ["COUNTED", "DUPLICATE"])

    def test_apn_formats_match(self):
        r = tally(parcels(3), [sub(1, "Owner Number1", "900000001"), sub(2, "Owner Number1", "900-000-001 ")])
        self.assertEqual(r["counted_protests"], 1)

    def test_one_letter_listing_two_parcels_counts_both(self):
        p = parcels(3)
        p[1]["record_owners"] = "Owner Number1"
        r = tally(p, [sub(1, "Owner Number1", "900-000-001; 900-000-002")])
        self.assertEqual(r["counted_protests"], 2)

    def test_resolve_by_account_then_address(self):
        r = tally(parcels(3), [sub(1, "Tina Tenant", account_no="a-1"), sub(2, "Owner Number2", service_address="2 Test Rd.")], self.ACCT)
        self.assertEqual(r["counted_protests"], 2)
        self.assertEqual([l.resolved_by for l in r["lines"]], ["account", "address"])

    def test_name_matching(self):
        self.assertTrue(t.names_match("Okafor, Daniel R.", "Daniel Okafor"))
        self.assertTrue(t.names_match("Daniel & Priya Okafor", "Priya Okafor"))
        self.assertFalse(t.names_match("Okafor", "Daniel Okafor"))
        self.assertFalse(t.names_match("Daniel Okafor", "Okafor Family Trust"))

    def test_order_of_input_does_not_change_result(self):
        s = [sub(1, "Owner Number1", "900-000-001"), sub(2, "Tina Tenant", "900-000-001"), sub(3, "Owner Number2", "900-000-002")]
        a, b = tally(parcels(3), s, self.ACCT), tally(parcels(3), list(reversed(s)), self.ACCT)
        key = lambda r: sorted((l.submission_id, l.status) for l in r["lines"])
        self.assertEqual(key(a), key(b))


class Validity(unittest.TestCase):
    def test_form_defects_are_not_counted(self):
        s = [sub(1, "Owner Number1", "900-000-001", signed="N"),
             sub(2, "Owner Number2", "900-000-002", channel="email"),
             sub(3, "Owner Number3", "900-000-003", received="2026-10-06T20:31:00")]
        r = tally(parcels(5), s)
        self.assertEqual((r["counted_protests"], statuses(r)), (0, ["INVALID"] * 3))

    def test_received_at_close_counts(self):
        r = tally(parcels(5), [sub(1, "Owner Number1", "900-000-001", received="2026-10-06T20:30:00")])
        self.assertEqual(r["counted_protests"], 1)

    def test_withdrawal_and_reprotest(self):
        s = [sub(1, "Owner Number1", "900-000-001", received="2026-09-01T10:00:00"),
             sub(2, "Owner Number1", "900-000-001", received="2026-09-02T10:00:00", action="withdraw")]
        self.assertEqual(tally(parcels(3), s)["counted_protests"], 0)
        s.append(sub(3, "Owner Number1", "900-000-001", received="2026-09-03T10:00:00"))
        self.assertEqual(tally(parcels(3), s)["counted_protests"], 1)

    def test_withdrawal_leaves_other_signers_protest(self):
        acct = Dedupe.ACCT
        s = [sub(1, "Owner Number1", "900-000-001", received="2026-09-01T10:00:00"),
             sub(2, "Tina Tenant", "900-000-001", received="2026-09-02T10:00:00"),
             sub(3, "Owner Number1", "900-000-001", received="2026-09-03T10:00:00", action="withdraw")]
        r = tally(parcels(3), s, acct)
        self.assertEqual(r["counted_protests"], 1)
        self.assertEqual({l.submission_id: l.status for l in r["lines"]}["S-002"], "COUNTED")

    def test_review_items_make_a_close_result_undetermined(self):
        s = [sub(1, "Owner Number1", "900-000-001"), sub(2, "Stranger Person", "900-000-002")]
        r = tally(parcels(3), s)
        self.assertEqual((r["counted_protests"], r["threshold"], r["outcome"]), (1, 2, "UNDETERMINED_PENDING_REVIEW"))

    def test_review_on_already_counted_parcel_adds_nothing(self):
        s = [sub(1, "Owner Number1", "900-000-001"), sub(2, "Stranger Person", "900-000-001")]
        r = tally(parcels(3), s)
        self.assertEqual((r["review_items_that_could_add_a_parcel"], r["outcome"]), (0, "NO_MAJORITY_PROTEST"))


class Assessment(unittest.TestCase):
    P = [{"apn": "970-1", "assessment_cents": "100000", "owners": "Ann Able"},
         {"apn": "970-2", "assessment_cents": "60000", "owners": "Bo Baker:3/4|Cy Baker:1/4"},
         {"apn": "970-3", "assessment_cents": "30000", "owners": "Di Cole"}]

    def b(self, i, apn, who, vote, **kw):
        d = {"ballot_id": "B-%d" % i, "received": "2026-09-0%dT10:00:00" % i, "apn": apn, "owner_name": who, "vote": vote, "signed": "Y"}
        d.update(kw)
        return d

    def test_weighting_beats_head_count(self):
        r = t.tally_assessment(self.P, [self.b(1, "970-1", "Ann Able", "yes"), self.b(2, "970-2", "Bo Baker", "no"),
                                        self.b(3, "970-3", "Di Cole", "no")], CLOSE)
        self.assertEqual((r["weighted_yes_exact"], r["weighted_no_exact"], r["majority_protest"]), ("100000", "90000", False))

    def test_co_owner_split_by_interest(self):
        r = t.tally_assessment(self.P, [self.b(1, "970-2", "Bo Baker", "no"), self.b(2, "970-2", "Cy Baker", "yes")], CLOSE)
        self.assertEqual((r["weighted_no_exact"], r["weighted_yes_exact"]), ("45000", "15000"))

    def test_tie_is_not_a_majority_protest(self):
        p = [dict(self.P[0]), dict(self.P[0], apn="970-9", owners="Ed Dunn")]
        r = t.tally_assessment(p, [self.b(1, "970-1", "Ann Able", "yes"), self.b(2, "970-9", "Ed Dunn", "no")], CLOSE)
        self.assertFalse(r["majority_protest"])

    def test_changed_ballot_replaces_earlier_one(self):
        r = t.tally_assessment(self.P, [self.b(1, "970-1", "Ann Able", "yes"), self.b(2, "970-1", "Ann Able", "no")], CLOSE)
        self.assertEqual((r["weighted_yes_exact"], r["weighted_no_exact"]), ("0", "100000"))

    def test_unsigned_and_withdrawn(self):
        r = t.tally_assessment(self.P, [self.b(1, "970-1", "Ann Able", "no", signed="N"), self.b(2, "970-3", "Di Cole", "no"),
                                        self.b(3, "970-3", "Di Cole", "withdraw")], CLOSE)
        self.assertEqual(r["weighted_no_exact"], "0")

    def test_missing_interests_go_to_review(self):
        p = [dict(self.P[1], owners="Bo Baker|Cy Baker")]
        r = t.tally_assessment(p, [self.b(1, "970-2", "Bo Baker", "no"), self.b(2, "970-2", "Cy Baker", "yes")], CLOSE)
        self.assertEqual((r["parcels_in_review"], r["weighted_no_exact"]), (["9702"], "0"))


CASE = {"proceeding": "section_6_fee", "service": "water", "notice_mailed": "2026-08-03", "hearing_date": "2026-10-06",
        "hearing_close": "2026-10-06T20:30:00", "adoption_date": "2026-10-06", "effective_date": "2027-01-01",
        "ab2257": {"proposed_fee_available": "2026-08-03", "objection_deadline": "2026-09-17T17:00:00",
                   "notice": {"written_basis_on_website": True, "website_link_in_notice": True,
                              "exhaustion_statement_prominent": True, "objection_requirements_stated": True,
                              "sol_120_day_statement": True}, "written_basis_mail_requests": []}}


class Calendar(unittest.TestCase):
    def results(self, **changes):
        c = copy.deepcopy(CASE)
        for k, v in changes.items():
            (c["ab2257"] if k in c["ab2257"] else c)[k] = v
        return {x.id: x.ok for x in t.check_calendar(c, RULES)}

    def test_all_pass_at_exactly_45_days(self):
        self.assertTrue(all(self.results().values()))

    def test_44_days_fails(self):
        r = self.results(objection_deadline="2026-09-16T17:00:00")
        self.assertFalse(r["objection_window"]); self.assertFalse(r["fee_available"])
        self.assertFalse(self.results(hearing_date="2026-09-16")["hearing_gap"])
        self.assertTrue(self.results(hearing_date="2026-09-17", objection_deadline="2026-09-17T09:00:00")["hearing_gap"])

    def test_refuse_fee_is_outside_ab2257(self):
        self.assertFalse(self.results(service="refuse")["ab2257_scope"])

    def test_sol_runs_from_later_date(self):
        s = t.sol_deadline(CASE, RULES)
        self.assertEqual((s["runs_from"], s["last_day_raw"], s["falls_on_weekend"]), ("2027-01-01", "2027-05-01", True))
        c = dict(CASE, effective_date="2026-10-01")
        self.assertEqual(t.sol_deadline(c, RULES)["last_day_raw"], "2027-02-03")
        self.assertIsNone(t.sol_deadline(dict(CASE, service="refuse"), RULES))
        self.assertIsNone(t.sol_deadline(dict(CASE, adoption_date="2021-12-01", effective_date="2021-12-01"), RULES))


class Gate(unittest.TestCase):
    OBJ = [{"objection_id": "OBJ-1", "received": "2026-09-10T10:00:00", "grounds_text": "Tier 3 exceeds cost."},
           {"objection_id": "OBJ-2", "received": "2026-09-17T17:00:00", "grounds_text": "Hydrant costs."},
           {"objection_id": "OBJ-3", "received": "2026-09-17T17:01:00", "grounds_text": "Late."}]

    def resp(self, oid, **kw):
        d = {"objection_id": oid, "responded_at": "2026-10-01T09:00:00", "exhibit_ref": "Exh. C",
             "explains_substantive_basis": "Y", "presented_to_board_at": "2026-10-06T18:00:00"}
        d.update(kw)
        return d

    def gate(self, responses, subs=()):
        return t.objection_gate(CASE, self.OBJ, responses, list(subs), RULES)

    def test_clear_when_every_timely_objection_is_answered(self):
        g = self.gate([self.resp("OBJ-1"), self.resp("OBJ-2")])
        self.assertEqual((g["gate"], g["timely_objections"], g["untimely"]), ("CLEAR", 2, 1))

    def test_one_missing_response_blocks(self):
        g = self.gate([self.resp("OBJ-1")])
        self.assertEqual((g["gate"], g["open"]), ("BLOCKED", ["OBJ-2"]))

    def test_late_or_unpresented_or_bare_response_blocks(self):
        for bad in ({"responded_at": "2026-10-06T20:31:00"}, {"presented_to_board_at": ""},
                    {"presented_to_board_at": "2026-10-07T09:00:00"}, {"explains_substantive_basis": "N"}):
            g = self.gate([self.resp("OBJ-1"), self.resp("OBJ-2", **bad)])
            self.assertEqual(g["open"], ["OBJ-2"], bad)

    def test_untriaged_protest_letter_blocks_until_triaged(self):
        ok = [self.resp("OBJ-1"), self.resp("OBJ-2")]
        letter = sub(1, "Owner Number1", "900-000-001", letter_text="The tiers violate Proposition 218.")
        self.assertEqual(self.gate(ok, [letter])["gate"], "BLOCKED")
        self.assertEqual(self.gate(ok, [dict(letter, objection_triage="bare_protest")])["gate"], "CLEAR")
        self.assertEqual(self.gate(ok, [dict(letter, letter_text="Rates are too high.")])["gate"], "CLEAR")

    def test_record_index_flags_missing_category(self):
        idx = t.record_index({"record_documents": [{"category": "A", "title": "Study"}]}, RULES)
        self.assertEqual([x["category"] for x in idx if not x["present"]], list("BCDEFGH"))


class RulesFile(unittest.TestCase):
    def test_every_rule_has_source_and_status(self):
        for k, r in RULES["rules"].items():
            self.assertTrue(r.get("source"), k)
            self.assertIn(r.get("status"), {"verified_primary", "not_verified"}, k)

    def test_engine_does_not_depend_on_unverified_rules(self):
        src = (ROOT / "tabulator.py").read_text(encoding="utf-8")
        for k, r in RULES["rules"].items():
            if r["status"] != "verified_primary":
                self.assertNotIn('"%s"' % k, src)


class Sample(unittest.TestCase):
    def test_sample_run_is_stable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            a = t.run(ROOT / "sample_data", Path(d) / "a")
            b = t.run(ROOT / "sample_data", Path(d) / "b")
            self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
            self.assertEqual((Path(d) / "a" / "protest_audit_log.csv").read_bytes(), (Path(d) / "b" / "protest_audit_log.csv").read_bytes())
        pt = a["protest_tally"]
        self.assertEqual((pt["identified_parcels"], pt["threshold"], pt["counted_protests"], pt["outcome"]),
                         (400, 201, 147, "NO_MAJORITY_PROTEST"))
        self.assertEqual((a["objection_gate"]["gate"], a["objection_gate"]["open"]), ("BLOCKED", ["OBJ-007", "OBJ-009"]))


if __name__ == "__main__":
    unittest.main()
