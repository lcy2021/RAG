from engine.headings import split_by_heading
from engine.retrieval import bm25_scores, reciprocal_rank_fusion, tokenize
from engine.runner import _safe_meta, ordered_calls
from models.enums import PipelineKind


def test_heading_split_keeps_titles() -> None:
    text = "# Refund\n\nYou may refund in 7 days.\n\n## Process\n\nSubmit a ticket."
    sections = split_by_heading(text)
    titles = [item["title"] for item in sections]
    assert "Refund" in titles
    assert "Process" in titles


def test_bm25_ranks_exact_terms_higher() -> None:
    docs = [tokenize("alpha beta"), tokenize("gamma LSTM Transformer"), tokenize("unrelated")]
    scores = bm25_scores(tokenize("LSTM Transformer"), docs)
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]


def test_rrf_merges_two_retrievers() -> None:
    dense = [{"chunk_id": "a", "content": "a"}, {"chunk_id": "b", "content": "b"}]
    sparse = [{"chunk_id": "b", "content": "b"}, {"chunk_id": "c", "content": "c"}]
    fused = reciprocal_rank_fusion([dense, sparse], k=60)
    ids = [item["chunk_id"] for item in fused]
    assert ids[0] == "b"
    assert set(ids) == {"a", "b", "c"}


def test_ensemble_retrievers_emit_parallel_calls() -> None:
    slots = [
        {
            "stage": "retriever",
            "mode": "ensemble",
            "bindings": [
                {"name": "dense", "params": {"top_k": 10}},
                {"name": "bm25", "params": {"top_k": 10}},
            ],
        },
        {"stage": "fusion", "bindings": [{"name": "rrf", "params": {"k": 60}}]},
    ]
    calls = ordered_calls(slots, PipelineKind.QUERY)
    retriever = next(item for item in calls if item["stage"] == "retriever")
    assert "parallel" in retriever
    assert {item["plugin"] for item in retriever["parallel"]} == {"dense", "bm25"}


def test_safe_meta_reports_per_plugin_retrieval() -> None:
    data = {
        "query": "q",
        "retrieved": [],
        "retrieved_lists": {
            "dense": [
                {"chunk_id": "a", "content": "alpha", "score": 0.9},
                {"chunk_id": "b", "content": "beta"},
            ],
            "bm25": [],
        },
        "answer": "should not leak into retriever meta",
    }
    meta = _safe_meta(data, "retriever")
    assert meta["retrieved_count"] == 0
    assert meta["retrieved_by_plugin"] == {"dense": 2, "bm25": 0}
    assert meta["passages"] == []
    assert meta["passages_by_plugin"]["dense"][0]["content"] == "alpha"
    assert meta["passages_by_plugin"]["dense"][0]["score"] == 0.9
    assert "answer" not in meta
    assert "answer_preview" not in meta


def test_safe_meta_is_stage_scoped() -> None:
    data = {
        "query": "q",
        "rewritten_query": "q2",
        "retrieved": [
            {
                "chunk_id": "a",
                "content": "passage body",
                "score": 0.8,
                "rerank_score": 0.95,
                "grade": 0.7,
            }
        ],
        "retrieved_lists": {"dense": [{"chunk_id": "a", "content": "passage body"}]},
        "answer": "final [1]",
        "crag_action": "correct",
        "crag_max_score": 0.9,
    }
    assert _safe_meta(data, "query_transformer") == {
        "query": "q",
        "rewritten_query": "q2",
    }
    fusion = _safe_meta(data, "fusion")
    assert fusion["retrieved_count"] == 1
    assert fusion["fused_list_count"] == 1
    assert fusion["passages"][0]["content"] == "passage body"
    assert fusion["passages"][0]["score"] == 0.8
    assert _safe_meta(data, "generator") == {
        "answer_preview": "final [1]",
        "citation_marks": ["[1]"],
    }
    grader = _safe_meta(data, "grader")
    assert grader["crag_action"] == "correct"
    assert grader["crag_max_score"] == 0.9
    assert grader["retrieved_count"] == 1
    assert grader["passages"][0]["grade"] == 0.7
