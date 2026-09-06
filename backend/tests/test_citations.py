from engine.citations import citation_ranks, citation_spans, normalize_sources


def test_citation_ranks_unique_in_order() -> None:
    assert citation_ranks("See [2] then [1] and again [2].") == [2, 1]


def test_citation_spans_offsets() -> None:
    text = "Alpha [1] beta [2]"
    spans = citation_spans(text)
    assert [(s["rank"], s["quote"], text[s["char_start"] : s["char_end"]]) for s in spans] == [
        (1, "[1]", "[1]"),
        (2, "[2]", "[2]"),
    ]


def test_normalize_sources_marks_cited() -> None:
    retrieved = [
        {"rank": 1, "chunk_id": None, "content": "a", "score": 0.9, "retriever": "dense"},
        {"rank": 2, "chunk_id": None, "content": "b", "score": 0.8, "retriever": "dense"},
    ]
    sources = normalize_sources(retrieved, answer="Answer cites [2] only.")
    assert sources[0]["cited"] is False
    assert sources[1]["cited"] is True
