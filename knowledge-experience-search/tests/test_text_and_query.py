import pytest

from kx.search import QueryError, normalise_filters, parse_query
from kx.text import query_terms, stem, tokenize


def test_tokenize_lowercases_and_splits_hyphens():
    assert tokenize("Earn-Out Provisions") == ["earn", "out", "provision"]


def test_stemmer_only_folds_plurals():
    assert stem("covenants") == "covenant"
    assert stem("parties") == "party"
    assert stem("basis") == "basis"      # not a plural
    assert stem("class") == "class"
    assert stem("status") == "status"
    assert stem("drafting") == "drafting"  # no verb stemming, by design


def test_possessive_is_dropped():
    assert tokenize("the client's board") == ["the", "client", "board"]


def test_query_terms_drop_stop_words_and_duplicates():
    assert query_terms("the motion to dismiss the motion") == ["motion", "dismiss"]


def test_parse_query_separates_terms_phrases_and_filters():
    parsed = parse_query('earn-out "milestone payment" type:memo practice:"Corporate and M&A"')
    assert parsed["terms"] == ["earn", "out"]
    assert parsed["phrases"] == [["milestone", "payment"]]
    assert parsed["filters"] == {"doc_type": "memo", "practice": "Corporate and M&A"}


def test_phrase_keeps_stop_words_for_positions():
    assert parse_query('"motion to dismiss"')["phrases"] == [["motion", "to", "dismiss"]]


def test_unknown_prefix_is_text_not_a_filter():
    parsed = parse_query("section:4 indemnity")
    assert parsed["filters"] == {}
    assert "section" in parsed["terms"] and "indemnity" in parsed["terms"]


def test_filter_aliases_map_to_canonical_names():
    assert parse_query("court:Tavish mtype:merger")["filters"] == {
        "jurisdiction": "Tavish", "matter_type": "merger"}


def test_boolean_filter_rejects_nonsense():
    assert normalise_filters({"filed": "yes"}) == {"was_filed": 1}
    with pytest.raises(QueryError):
        normalise_filters({"filed": "perhaps"})


def test_unknown_filter_key_is_an_error():
    with pytest.raises(QueryError):
        normalise_filters({"colour": "blue"})
