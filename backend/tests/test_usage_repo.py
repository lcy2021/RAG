"""Unit tests for usage aggregation helpers."""

from repositories.usage import _empty_bucket, _merge_buckets


def test_merge_buckets_sums_tokens_and_cost():
    left = {
        "run_count": 2,
        "token_in": 10,
        "token_out": 4,
        "token_cached": 3,
        "cost_micros": 100,
    }
    right = {
        "run_count": 3,
        "token_in": 5,
        "token_out": 6,
        "token_cached": 2,
        "cost_micros": 50,
    }
    merged = _merge_buckets(left, right)
    assert merged == {
        "run_count": 5,
        "token_in": 15,
        "token_out": 10,
        "token_cached": 5,
        "cost_micros": 150,
    }


def test_merge_buckets_keeps_null_cost_when_both_missing():
    merged = _merge_buckets(_empty_bucket(), _empty_bucket())
    assert merged["cost_micros"] is None
    assert merged["run_count"] == 0


def test_merge_buckets_treats_partial_cost_as_zero_plus_known():
    left = _empty_bucket()
    right = {
        "run_count": 1,
        "token_in": 3,
        "token_out": 1,
        "token_cached": 2,
        "cost_micros": 20,
    }
    merged = _merge_buckets(left, right)
    assert merged["cost_micros"] == 20
    assert merged["token_in"] == 3
    assert merged["token_cached"] == 2
