import json
import shutil

import pytest

from kx import config as cfg
from sources.base import SourceAdapter, SourceError
from sources.mapping import RejectedRow, load_mapping, map_row
from sources.synthetic_files import SyntheticFileAdapter


@pytest.fixture(scope="module")
def mapping():
    return load_mapping(cfg.DEFAULT_MAPPING_PATH)


def test_mapping_renames_columns_and_translates_codes(mapping):
    row = {"MatterNo": "M1", "MatterName": "X", "SecurityCode": "R", "PracticeArea": "Tax"}
    out = map_row(row, mapping["matters"])
    assert out["matter_id"] == "M1" and out["security"] == "restricted" and out["practice"] == "Tax"


def test_unmapped_security_code_passes_through_as_unknown(mapping):
    out = map_row({"MatterNo": "M1", "SecurityCode": "Z9"}, mapping["matters"])
    assert out["security"] == "Z9"  # not "public": the permission model will deny it


def test_missing_security_code_is_not_defaulted_to_public(mapping):
    assert map_row({"MatterNo": "M1"}, mapping["matters"])["security"] == ""


def test_missing_required_field_rejects_the_row(mapping):
    with pytest.raises(RejectedRow):
        map_row({"DocName": "No id"}, mapping["documents"])


def test_types_and_flags_are_converted(mapping):
    row = {"DocId": "D1", "MatterNo": "M1", "DocName": "T", "Version": "3", "Final": "Y",
           "Filed": "N", "ModelForm": "maybe", "ReuseCount": "7", "Class": "BRF"}
    out = map_row(row, mapping["documents"])
    assert out["version_no"] == 3 and out["reuse_count"] == 7
    assert out["is_final"] is True and out["was_filed"] is False
    assert out["model_form"] is False  # unrecognised flag is treated as not set
    assert out["doc_type"] == "brief"


def test_unknown_document_class_becomes_other(mapping):
    out = map_row({"DocId": "D1", "MatterNo": "M1", "DocName": "T", "Class": "???"},
                  mapping["documents"])
    assert out["doc_type"] == "other"


def test_synthetic_adapter_implements_the_interface(full_adapter):
    assert isinstance(full_adapter, SourceAdapter)
    assert SourceAdapter.__abstractmethods__ == {
        "people", "matters", "permissions", "matter_team", "time_entries", "document_changes"}


def test_synthetic_adapter_reads_the_whole_corpus(canonical, manifest):
    assert len(canonical["documents"]) == manifest["counts"]["documents"]
    assert len(canonical["matters"]) == manifest["counts"]["matters"]
    assert len(canonical["people"]) == manifest["counts"]["people"]
    assert len(canonical["permissions"].walls) == 3


def _copy_small(data_dir, tmp_path):
    for name in ("people.csv", "group_members.csv", "matters.csv", "matter_access.csv",
                 "walls.csv", "wall_members.csv", "matter_team.csv", "time_entries.csv",
                 "deletions.jsonl"):
        shutil.copy(data_dir / name, tmp_path / name)
    with open(data_dir / "documents.jsonl", encoding="utf-8") as fh:
        lines = [next(fh) for _ in range(20)]
    (tmp_path / "documents.jsonl").write_text("".join(lines), encoding="utf-8")
    return SyntheticFileAdapter(tmp_path, cfg.DEFAULT_MAPPING_PATH)


def test_missing_permission_file_raises_instead_of_assuming_no_walls(data_dir, tmp_path):
    adapter = _copy_small(data_dir, tmp_path)
    (tmp_path / "walls.csv").unlink()
    with pytest.raises(SourceError):
        adapter.permissions()


def test_wall_with_no_listed_members_is_reported_as_unknown_not_empty(data_dir, tmp_path):
    adapter = _copy_small(data_dir, tmp_path)
    (tmp_path / "wall_members.csv").write_text("WallId,ExcludedUserId\n", encoding="utf-8")
    walls = adapter.permissions().walls
    assert walls and all(w.excluded_person_ids is None for w in walls)


def test_malformed_permission_row_stops_the_sync(data_dir, tmp_path):
    adapter = _copy_small(data_dir, tmp_path)
    with open(tmp_path / "wall_members.csv", "a", encoding="utf-8") as fh:
        fh.write("W1,\n")  # a wall row with no person
    with pytest.raises(SourceError):
        adapter.permissions()


def test_document_changes_honours_cursor_and_tombstones(data_dir, tmp_path):
    adapter = _copy_small(data_dir, tmp_path)
    first = adapter.document_changes(None)
    assert len(first.upserts) == 20 and first.cursor
    later = "2031-01-01T00:00:00"
    with open(tmp_path / "documents.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"DocId": "D-NEW", "MatterNo": "M0001", "DocName": "New memo",
                             "Text": "new text here today", "Class": "MEM",
                             "Modified": later}) + "\n")
    (tmp_path / "deletions.jsonl").write_text(
        json.dumps({"DocId": "D00001", "DeletedAt": later}) + "\n", encoding="utf-8")
    second = adapter.document_changes(first.cursor)
    assert "D-NEW" in [d.doc_id for d in second.upserts]
    assert len(second.upserts) < 20
    assert second.deleted_doc_ids == ("D00001",)
    assert second.cursor == later


def test_bad_document_row_is_rejected_and_reported_not_fatal(data_dir, tmp_path):
    adapter = _copy_small(data_dir, tmp_path)
    with open(tmp_path / "documents.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"DocName": "orphan with no id"}) + "\n")
    batch = adapter.document_changes(None)
    assert len(batch.upserts) == 20
    assert len(batch.rejected) == 1 and "doc_id" in batch.rejected[0][1]
