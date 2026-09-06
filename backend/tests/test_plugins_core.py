import pytest
from pydantic import ValidationError

from engine.param_merge import merge_params
from models.schemas import SlotBindingIn
from plugins import define_stage


def test_merge_params_layers() -> None:
    merged = merge_params({"a": 1, "b": 2}, {"b": 3}, {"c": 4})
    assert merged == {"a": 1, "b": 3, "c": 4}


def test_define_stage_rejects_api_key() -> None:
    with pytest.raises(ValueError, match="secret keys"):
        define_stage(stage="generator", name="bad", default_params={"api_key": "x"})


def test_slot_binding_rejects_api_key() -> None:
    with pytest.raises(ValidationError):
        SlotBindingIn(name="chat", params={"api_key": "x"})
