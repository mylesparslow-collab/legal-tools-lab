#!/usr/bin/env python3
"""Check every corpus document and answer key. Exit 1 if any problem is found.

Usage: python3 check_corpus.py [doc_id ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.corpus import list_doc_ids, load_document, validate_document  # noqa: E402


def main(argv: list[str]) -> int:
    ids = argv or list_doc_ids()
    bad = 0
    for doc_id in ids:
        problems = validate_document(doc_id)
        if problems:
            bad += 1
            print("\n".join(problems))
        else:
            doc = load_document(doc_id)
            print(f"ok  {doc_id}: {doc.word_count} words, {len(doc.defects)} defects")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
