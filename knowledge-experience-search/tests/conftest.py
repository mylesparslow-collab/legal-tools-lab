import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kx import acl, config as cfg, index  # noqa: E402
from sources.memory import MemoryAdapter  # noqa: E402
from sources.synthetic_files import SyntheticFileAdapter  # noqa: E402

DATA = ROOT / "data" / "synthetic"


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory):
    """The committed synthetic corpus, or a fresh one if it has not been generated."""
    if (DATA / "documents.jsonl").exists():
        return DATA
    from synth.generate import generate
    out = tmp_path_factory.mktemp("synthetic")
    generate(out)
    return out


@pytest.fixture(scope="session")
def key(data_dir):
    return json.loads((data_dir / "ANSWER_KEY.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def manifest(data_dir):
    return json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def config():
    return cfg.load_config()


@pytest.fixture(scope="session")
def full_adapter(data_dir):
    return SyntheticFileAdapter(data_dir, cfg.DEFAULT_MAPPING_PATH)


@pytest.fixture(scope="session")
def full_db_path(tmp_path_factory, full_adapter):
    path = tmp_path_factory.mktemp("index") / "full.sqlite"
    conn = index.connect(path)
    index.Indexer(conn).sync(full_adapter, full=True)
    conn.close()
    return path


@pytest.fixture(scope="session")
def full(full_db_path):
    """Read-only connection to an index of the whole synthetic corpus."""
    conn = index.connect(full_db_path, readonly=True)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def canonical(full_adapter):
    """The whole corpus as canonical records, for building filtered worlds."""
    return {
        "people": full_adapter.people(), "matters": full_adapter.matters(),
        "permissions": full_adapter.permissions(), "team": full_adapter.matter_team(),
        "time": full_adapter.time_entries(),
        "documents": list(full_adapter.document_changes(None).upserts),
    }


@pytest.fixture(scope="session")
def world_without_hidden(full, canonical):
    """Factory: an index that never contained anything the given user cannot see."""
    cache = {}

    def build(user_id):
        if user_id not in cache:
            visible = acl.visible_matter_ids(full, user_id)
            perms = canonical["permissions"]
            adapter = MemoryAdapter(
                people=canonical["people"],
                matters=[m for m in canonical["matters"] if m.matter_id in visible],
                group_members=perms.group_members,
                grants=[g for g in perms.grants if g.matter_id in visible],
                walls=[],  # every wall that touched this user's view is gone with its matters
                team=[t for t in canonical["team"] if t.matter_id in visible],
                time_entries=[t for t in canonical["time"] if t.matter_id in visible],
                documents=[d for d in canonical["documents"] if d.matter_id in visible])
            # Walls that exclude other people from still-visible matters must stay.
            adapter.walls = [type(w)(w.wall_id, tuple(m for m in w.matter_ids if m in visible),
                                     w.excluded_person_ids)
                             for w in perms.walls if any(m in visible for m in w.matter_ids)]
            conn = index.connect(":memory:")
            index.Indexer(conn).sync(adapter, full=True)
            cache[user_id] = conn
        return cache[user_id]

    return build
